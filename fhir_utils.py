import re
from fhir.resources.R4B.bundle import Bundle

def run_custom_logical_validations(bundle_dict):
    """Performs referential integrity and UUID format checks."""
    errors = []
    entries = bundle_dict.get("entry", [])

    if not entries:
        return ["Logical Error: Bundle contains no entries."]

    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    defined_urls = set()
    
    for entry in entries:
        if "fullUrl" in entry:
            defined_urls.add(entry["fullUrl"])
            if entry["fullUrl"].startswith("urn:uuid:"):
                uuid_str = entry["fullUrl"].replace("urn:uuid:", "")
                if not uuid_pattern.match(uuid_str):
                    errors.append(f"Logical Error: Invalid UUID format -> {uuid_str}")

        if "resource" in entry and "id" in entry["resource"]:
            res_type = entry["resource"]["resourceType"]
            res_id = entry["resource"]["id"]
            defined_urls.add(f"{res_type}/{res_id}")
            defined_urls.add(f"urn:uuid:{res_id}")

    def find_all_references(obj):
        refs = []
        if isinstance(obj, dict):
            if "reference" in obj and isinstance(obj["reference"], str):
                refs.append(obj["reference"])
            for v in obj.values():
                refs.extend(find_all_references(v))
        elif isinstance(obj, list):
            for item in obj:
                refs.extend(find_all_references(item))
        return refs

    all_references = find_all_references(entries)
    for ref in all_references:
        if ref.startswith("http"): continue
        if ref not in defined_urls:
            errors.append(f"Logical Error: Broken Link! Reference '{ref}' missing.")

    return errors