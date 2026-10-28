"""Portable worker artifacts contain only the already reviewed ancestor packet."""

import io
import zipfile

from .context import WorkerPacket, canonical, verify_packet


def export_worker_bundle(packet: WorkerPacket) -> bytes:
    verify_packet(packet)
    members = packet.documents | {"manifest.json": canonical(packet.manifest) + "\n"}
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, text.encode("utf-8"))
    return output.getvalue()
