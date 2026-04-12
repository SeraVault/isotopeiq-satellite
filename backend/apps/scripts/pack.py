"""
Script Pack — portable export / import format for Script Jobs.

A pack is a plain JSON document that bundles all Script records referenced by
a ScriptJob together with the job definition itself.  Packs are self-contained
and can be shared as files, GitHub Gists, or hosted in a community catalogue.

Pack format
-----------
{
  "format":  "isotopeiq-script-pack",
  "version": "1",
  "metadata": {
    "name":         str,   # human-readable pack name (defaults to job name)
    "description":  str,
    "author":       str,   # optional, free text
    "pack_version": str,   # semver of the pack itself, separate from script versions
    "tags":         [str]  # free-form labels for discovery / filtering
  },
  "scripts": [
    {
      "name":        str,  # must be unique within the pack; used as step reference
      "description": str,
      "script_type": collection | parser | deployment | utility,
      "run_on":      client | server | both,
      "language":    str,
      "version":     str,
      "content":     str   # full script body
    },
    ...
  ],
  "script_jobs": [
    {
      "name":        str,
      "description": str,
      "job_type":    str,  # baseline_collection | remediation | … | custom
      "steps": [
        {
          "order":          int,
          "script":         str,  # references scripts[].name
          "pipe_to_next":   bool,
          "save_output":    bool,
          "enable_baseline": bool,
          "enable_drift":   bool
        },
        ...
      ]
    },
    ...
  ]
}

Import behaviour
----------------
By default (overwrite=False) an existing Script or ScriptJob with the same
name is left untouched and its existing record is used when wiring steps.
Set overwrite=True to replace the script content / job definition.
"""

from django.db import transaction

from .job_models import ScriptJob, ScriptJobStep
from .models import Script

PACK_FORMAT = "isotopeiq-script-pack"
PACK_VERSION = "1"


# ── Export ────────────────────────────────────────────────────────────────────

def export_script_job(script_job: ScriptJob) -> dict:
    """Serialise a ScriptJob and all its referenced Scripts into a pack dict."""
    steps = list(script_job.steps.select_related("script").order_by("order"))
    # De-duplicate scripts while preserving insertion-friendly ordering.
    seen: dict[int, Script] = {}
    for step in steps:
        if step.script_id not in seen:
            seen[step.script_id] = step.script
    scripts = list(seen.values())

    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "metadata": {
            "name": script_job.name,
            "description": script_job.description,
            "author": "",
            "pack_version": "1.0.0",
            "tags": [],
        },
        "scripts": [
            {
                "name": s.name,
                "description": s.description,
                "script_type": s.script_type,
                "run_on": s.run_on,
                "language": s.language,
                "version": s.version,
                "content": s.content,
            }
            for s in scripts
        ],
        "script_jobs": [
            {
                "name": script_job.name,
                "description": script_job.description,
                "job_type": script_job.job_type,
                "steps": [
                    {
                        "order": step.order,
                        "script": step.script.name,
                        "pipe_to_next": step.pipe_to_next,
                        "save_output": step.save_output,
                        "enable_baseline": step.enable_baseline,
                        "enable_drift": step.enable_drift,
                    }
                    for step in steps
                ],
            }
        ],
    }


# ── Import ────────────────────────────────────────────────────────────────────

def import_script_pack(data: dict, overwrite: bool = False) -> dict:
    """
    Import a script pack dict, creating Scripts and ScriptJobs as needed.

    Returns a summary:
        {
            "created_scripts":  [str, ...],
            "updated_scripts":  [str, ...],
            "skipped_scripts":  [str, ...],
            "created_jobs":     [str, ...],
            "updated_jobs":     [str, ...],
            "skipped_jobs":     [str, ...],
        }
    """
    fmt = data.get("format")
    ver = str(data.get("version", ""))
    if fmt != PACK_FORMAT:
        raise ValueError(f"Unknown pack format: {fmt!r}. Expected {PACK_FORMAT!r}.")
    if ver != PACK_VERSION:
        raise ValueError(f"Unsupported pack version: {ver!r}. Expected {PACK_VERSION!r}.")

    created_scripts: list[str] = []
    updated_scripts: list[str] = []
    skipped_scripts: list[str] = []
    created_jobs:    list[str] = []
    updated_jobs:    list[str] = []
    skipped_jobs:    list[str] = []

    # Map script name → Script instance; populated during the scripts phase and
    # reused when wiring job steps.
    script_map: dict[str, Script] = {}

    with transaction.atomic():
        # ── Scripts ───────────────────────────────────────────────────────────
        for s_data in data.get("scripts", []):
            name = s_data.get("name", "").strip()
            if not name:
                raise ValueError("Script entry is missing a 'name' field.")

            existing = Script.objects.filter(name=name).first()
            if existing:
                if overwrite:
                    for field in ("description", "script_type", "run_on",
                                  "language", "version", "content"):
                        setattr(existing, field,
                                s_data.get(field, getattr(existing, field)))
                    existing.save()
                    script_map[name] = existing
                    updated_scripts.append(name)
                else:
                    script_map[name] = existing
                    skipped_scripts.append(name)
            else:
                script = Script.objects.create(
                    name=name,
                    description=s_data.get("description", ""),
                    script_type=s_data["script_type"],
                    run_on=s_data.get("run_on", "client"),
                    language=s_data.get("language", "shell"),
                    version=s_data.get("version", "1.0.0"),
                    content=s_data["content"],
                )
                script_map[name] = script
                created_scripts.append(name)

        # ── Script Jobs ───────────────────────────────────────────────────────
        for j_data in data.get("script_jobs", []):
            name = j_data.get("name", "").strip()
            if not name:
                raise ValueError("Script job entry is missing a 'name' field.")

            existing_job = ScriptJob.objects.filter(name=name).first()

            if existing_job and not overwrite:
                skipped_jobs.append(name)
                continue

            if existing_job:
                existing_job.description = j_data.get("description", existing_job.description)
                existing_job.job_type    = j_data.get("job_type", existing_job.job_type)
                existing_job.save()
                existing_job.steps.all().delete()
                job = existing_job
                updated_jobs.append(name)
            else:
                job = ScriptJob.objects.create(
                    name=name,
                    description=j_data.get("description", ""),
                    job_type=j_data.get("job_type", "custom"),
                )
                created_jobs.append(name)

            for step_data in j_data.get("steps", []):
                script_name = step_data.get("script", "")
                if script_name not in script_map:
                    # Allow referencing a script that already exists in the DB
                    # but was not included in this pack's scripts[] array.
                    db_script = Script.objects.filter(name=script_name).first()
                    if db_script is None:
                        raise ValueError(
                            f"Job {name!r}: step references unknown script {script_name!r}. "
                            "Include it in the pack's 'scripts' array or ensure it already "
                            "exists on this Satellite."
                        )
                    script_map[script_name] = db_script

                ScriptJobStep.objects.create(
                    script_job=job,
                    order=step_data["order"],
                    script=script_map[script_name],
                    pipe_to_next=step_data.get("pipe_to_next", True),
                    save_output=step_data.get("save_output", False),
                    enable_baseline=step_data.get("enable_baseline", False),
                    enable_drift=step_data.get("enable_drift", False),
                )

    return {
        "created_scripts": created_scripts,
        "updated_scripts": updated_scripts,
        "skipped_scripts": skipped_scripts,
        "created_jobs":    created_jobs,
        "updated_jobs":    updated_jobs,
        "skipped_jobs":    skipped_jobs,
    }
