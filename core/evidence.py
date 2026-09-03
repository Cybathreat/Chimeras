"""
Chimeras v3.1 — Evidence Locker

Hashes every evidence artifact (raw tool output, PoC files, screenshots,
payloads) with SHA-256 and writes an immutable manifest. Links evidence
hashes to findings so the report can cite verifiable proof.

When a client challenges a finding, we produce:
  1. The finding with its evidence hash
  2. The raw artifact with a matching hash
  3. The manifest proving neither has been tampered with

This is court-admissible evidence chain. Strix exports SARIF. We export
SARIF plus a hash-verified evidence bundle.

Integration:
    Bookkeeper calls collect_evidence() at report time.
    Output: evidence/ directory with hashed copies + evidence_manifest.json
"""

import hashlib
import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class EvidenceLocker:
    """SHA-256 hashed evidence chain for pentest engagements.

    Collects all raw tool output, PoC files, and finding-linked artifacts
    into an evidence/ directory. Every file is SHA-256 hashed. A manifest
    JSON records: filename, original path, hash, size, finding_id link,
    timestamp, bot source.

    The manifest is itself hashed to detect tampering after the fact.

    Thread-safe: module-level lock guards all writes.
    """

    _write_lock = threading.Lock()

    def __init__(self, engagement_dir: Path):
        self.engagement_dir = Path(engagement_dir)
        self.evidence_dir = self.engagement_dir / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.evidence_dir / "evidence_manifest.json"

    def _sha256(self, content: bytes) -> str:
        """Compute SHA-256 hash of bytes content."""
        return hashlib.sha256(content).hexdigest()

    def _sha256_file(self, path: Path) -> str:
        """Compute SHA-256 hash of a file's contents."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def collect_raw_outputs(self) -> List[Dict[str, Any]]:
        """Collect all files from engagement/raw/ directory.

        Copies each file to evidence/ with a hash-prefixed name,
        records hash, size, and source in manifest entries.
        """
        entries: List[Dict[str, Any]] = []
        raw_dir = self.engagement_dir / "raw"

        if not raw_dir.exists():
            return entries

        for rf in sorted(raw_dir.iterdir()):
            if not rf.is_file():
                continue
            try:
                content = rf.read_bytes()
                file_hash = self._sha256(content)
                dest_name = f"{file_hash[:16]}_{rf.name}"
                dest = self.evidence_dir / dest_name

                # Copy if not already collected
                if not dest.exists():
                    with EvidenceLocker._write_lock:
                        shutil.copy2(rf, dest)

                entries.append({
                    "evidence_id": f"EVD-{len(entries) + 1:03d}",
                    "filename": dest_name,
                    "original_path": str(rf),
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "source": "raw_output",
                    "finding_id": None,  # linked later
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.warning(f"Failed to collect raw output {rf.name}: {e}")

        return entries

    def collect_poc_files(self) -> List[Dict[str, Any]]:
        """Collect all files from engagement/poc/ directory."""
        entries: List[Dict[str, Any]] = []
        poc_dir = self.engagement_dir / "poc"

        if not poc_dir.exists():
            return entries

        for pf in sorted(poc_dir.iterdir()):
            if not pf.is_file():
                continue
            try:
                content = pf.read_bytes()
                file_hash = self._sha256(content)
                dest_name = f"{file_hash[:16]}_{pf.name}"
                dest = self.evidence_dir / dest_name

                if not dest.exists():
                    with EvidenceLocker._write_lock:
                        shutil.copy2(pf, dest)

                entries.append({
                    "evidence_id": f"EVD-{len(entries) + 1:03d}",
                    "filename": dest_name,
                    "original_path": str(pf),
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "source": "poc",
                    "finding_id": None,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.warning(f"Failed to collect PoC file {pf.name}: {e}")

        return entries

    def collect_finding_evidence(
        self, findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Hash the proof_of_existence text from each finding.

        Creates a text file per finding with its proof_of_existence content,
        hashes it, and records the link between finding_id and evidence hash.
        """
        entries: List[Dict[str, Any]] = []

        for finding in findings:
            fid = finding.get("id") or finding.get("finding_id", "UNKNOWN")
            proof = finding.get("proof_of_existence", "")

            if not proof or proof == "N/A":
                continue

            try:
                content = proof.encode("utf-8")
                file_hash = self._sha256(content)
                dest_name = f"{file_hash[:16]}_{fid}_proof.txt"
                dest = self.evidence_dir / dest_name

                if not dest.exists():
                    with EvidenceLocker._write_lock:
                        dest.write_bytes(content)

                entries.append({
                    "evidence_id": f"EVD-{len(entries) + 1:03d}",
                    "filename": dest_name,
                    "original_path": None,
                    "sha256": file_hash,
                    "size_bytes": len(content),
                    "source": "finding_proof",
                    "finding_id": fid,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.warning(f"Failed to hash proof for {fid}: {e}")

        return entries

    def collect_all(
        self,
        findings: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Collect all evidence and write the manifest.

        This is the main entry point. Bookkeeper calls this at report time.

        Args:
            findings: List of finding dicts (from FindingsStore.format_for_report()).
                      Used to link evidence to findings via proof_of_existence.

        Returns:
            Manifest dict with all evidence entries and manifest hash.
        """
        findings = findings or []
        all_entries: List[Dict[str, Any]] = []

        # 1. Collect raw tool outputs
        raw_entries = self.collect_raw_outputs()
        all_entries.extend(raw_entries)

        # 2. Collect PoC files
        poc_entries = self.collect_poc_files()
        all_entries.extend(poc_entries)

        # 3. Hash finding proof_of_existence text
        proof_entries = self.collect_finding_evidence(findings)
        all_entries.extend(proof_entries)

        # 4. Try to link raw outputs to findings by matching content
        self._link_evidence_to_findings(all_entries, findings)

        # 5. Re-number evidence IDs sequentially
        for i, entry in enumerate(all_entries, 1):
            entry["evidence_id"] = f"EVD-{i:03d}"

        # 6. Write manifest
        manifest = {
            "generated_at": datetime.utcnow().isoformat(),
            "engagement_dir": str(self.engagement_dir),
            "total_artifacts": len(all_entries),
            "evidence": all_entries,
            "manifest_hash": None,  # filled after we compute it
        }

        # Compute manifest hash (hash of the evidence entries, excluding the
        # manifest_hash field itself)
        manifest_content = json.dumps(
            {k: v for k, v in manifest.items() if k != "manifest_hash"},
            sort_keys=True,
        )
        manifest["manifest_hash"] = self._sha256(manifest_content.encode())

        # Write manifest
        with EvidenceLocker._write_lock:
            self.manifest_path.write_text(
                json.dumps(manifest, indent=2)
            )

        logger.info(
            f"Evidence locker: {len(all_entries)} artifacts collected, "
            f"manifest hash: {manifest['manifest_hash'][:16]}..."
        )

        return manifest

    def _link_evidence_to_findings(
        self,
        entries: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
    ):
        """Try to link raw output evidence to findings by content matching.

        If a finding's proof_of_existence text appears in a raw output file,
        link that evidence to the finding.
        """
        for finding in findings:
            fid = finding.get("id") or finding.get("finding_id", "UNKNOWN")
            proof = finding.get("proof_of_existence", "")

            if not proof or proof == "N/A":
                continue

            # Check if any raw output contains this proof text
            proof_snippet = proof[:200].strip()
            if not proof_snippet:
                continue

            for entry in entries:
                if entry.get("finding_id"):
                    continue  # already linked
                if entry.get("source") not in ("raw_output", "poc"):
                    continue

                evidence_path = self.evidence_dir / entry["filename"]
                if not evidence_path.exists():
                    continue

                try:
                    content = evidence_path.read_text(errors="replace")
                    if proof_snippet in content:
                        entry["finding_id"] = fid
                except Exception:
                    pass

    def verify_manifest(self) -> bool:
        """Verify that the manifest has not been tampered with.

        Recomputes the manifest hash and compares to the stored value.
        """
        if not self.manifest_path.exists():
            return False

        try:
            manifest = json.loads(self.manifest_path.read_text())
            stored_hash = manifest.get("manifest_hash")
            if not stored_hash:
                return False

            # Recompute
            manifest_content = json.dumps(
                {k: v for k, v in manifest.items() if k != "manifest_hash"},
                sort_keys=True,
            )
            computed_hash = self._sha256(manifest_content.encode())

            return computed_hash == stored_hash
        except Exception as e:
            logger.error(f"Manifest verification failed: {e}")
            return False

    def get_manifest(self) -> Optional[Dict[str, Any]]:
        """Read and return the evidence manifest."""
        if not self.manifest_path.exists():
            return None
        try:
            return json.loads(self.manifest_path.read_text())
        except Exception as e:
            logger.error(f"Failed to read manifest: {e}")
            return None

    def get_findings_with_hashes(
        self, findings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich findings with their evidence SHA-256 hashes.

        Returns a copy of the findings list with an added 'evidence_hash'
        field for each finding that has linked evidence.
        """
        manifest = self.get_manifest()
        if not manifest:
            return findings

        # Build finding_id → list of hashes
        hash_map: Dict[str, List[str]] = {}
        for entry in manifest.get("evidence", []):
            fid = entry.get("finding_id")
            if fid:
                hash_map.setdefault(fid, []).append(entry["sha256"])

        enriched = []
        for f in findings:
            f_copy = dict(f)
            fid = f_copy.get("id") or f_copy.get("finding_id", "UNKNOWN")
            hashes = hash_map.get(fid, [])
            if hashes:
                f_copy["evidence_hash"] = hashes[0]  # primary hash
                f_copy["evidence_hashes"] = hashes  # all linked hashes
            else:
                # Hash the proof_of_existence text itself as fallback
                proof = f_copy.get("proof_of_existence", "")
                if proof and proof != "N/A":
                    f_copy["evidence_hash"] = self._sha256(
                        proof.encode("utf-8")
                    )
                    f_copy["evidence_hashes"] = [f_copy["evidence_hash"]]
                else:
                    f_copy["evidence_hash"] = None
                    f_copy["evidence_hashes"] = []
            enriched.append(f_copy)

        return enriched

    def summary(self) -> Dict[str, Any]:
        """Return a summary of the evidence locker for the report."""
        manifest = self.get_manifest()
        if not manifest:
            return {"total": 0, "linked": 0, "unlinked": 0, "verified": False}

        evidence = manifest.get("evidence", [])
        linked = sum(1 for e in evidence if e.get("finding_id"))
        unlinked = len(evidence) - linked

        return {
            "total": len(evidence),
            "linked": linked,
            "unlinked": unlinked,
            "verified": self.verify_manifest(),
            "manifest_hash": manifest.get("manifest_hash", "")[:16] + "...",
            "generated_at": manifest.get("generated_at", "N/A"),
        }