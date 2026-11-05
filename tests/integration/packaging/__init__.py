"""Guards the packaging boundary: the declarative package manifest is
path-safe, and both platform scripts consume it the same way.

Split into manifest/path-safety (test_manifest_path_safety) and script
parity (test_script_parity), sharing constants in _shared.py. The v3 Skills
are added to the manifest, with their archive checks, by #851.
"""
