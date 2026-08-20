"""
Crosswalk between NSF directorates and OpenAlex fields.

The two taxonomies answer different questions. An NSF directorate says *who
funds this*; an OpenAlex field says *what body of literature this belongs to*.
They overlap heavily but are not substitutable, and the mismatches are the
interesting part rather than noise to be smoothed over:

  - **OpenAlex covers research NSF does not fund.** All five Health Sciences
    fields (Medicine, Nursing, Dentistry, Veterinary, Health Professions) have
    no NSF directorate, because clinical medicine is NIH's remit. Nearly a fifth
    of the OpenAlex field space is unreachable from an NSF label.
  - **NSF has a directorate that is not a discipline.** Technology, Innovation
    and Partnerships is a funding *mechanism* — commercialisation and industry
    partnership — and TIP awards can come from any field. It is mapped to the
    business/engineering fields where such work is usually published, but the
    mapping is weak by nature and flagged as such.
  - **The mapping is many-to-many.** Materials Science and Energy sit between
    Engineering and Mathematical & Physical Sciences; Social Sciences receives
    both SBE and STEM Education, since OpenAlex has no Education field at this
    level (education is a *subfield* of Social Sciences).

Because of this, the crosswalk is a **documentation and analysis artefact**, not
a relabelling tool. Pushing gold-set `nsf_*` tags through it would manufacture
labels no human checked, and the resulting numbers would measure the crosswalk
rather than the tagger. Re-labelling for an OpenAlex evaluation has to be a
human pass; see Documentation/ANNOTATION_CODEBOOK.md.
"""

from typing import Dict, FrozenSet, List, Optional, Tuple

# NSF directorate -> OpenAlex fields it plausibly maps onto, best match first.
NSF_TO_OPENALEX: Dict[str, Tuple[str, ...]] = {
    "nsf_bio": (
        "oa_field_11",  # Agricultural and Biological Sciences
        "oa_field_13",  # Biochemistry, Genetics and Molecular Biology
        "oa_field_24",  # Immunology and Microbiology
        "oa_field_28",  # Neuroscience
    ),
    "nsf_cise": (
        "oa_field_17",  # Computer Science
        "oa_field_18",  # Decision Sciences
    ),
    # OpenAlex has no Education field; education is a subfield of Social
    # Sciences, so this is the closest available and is coarser than the NSF
    # directorate it comes from.
    "nsf_edu": (
        "oa_field_33",  # Social Sciences
    ),
    "nsf_eng": (
        "oa_field_22",  # Engineering
        "oa_field_15",  # Chemical Engineering
        "oa_field_25",  # Materials Science
        "oa_field_21",  # Energy
    ),
    "nsf_geo": (
        "oa_field_19",  # Earth and Planetary Sciences
        "oa_field_23",  # Environmental Science
    ),
    "nsf_mps": (
        "oa_field_31",  # Physics and Astronomy
        "oa_field_16",  # Chemistry
        "oa_field_26",  # Mathematics
        "oa_field_25",  # Materials Science
    ),
    "nsf_sbe": (
        "oa_field_33",  # Social Sciences
        "oa_field_32",  # Psychology
        "oa_field_20",  # Economics, Econometrics and Finance
        "oa_field_12",  # Arts and Humanities
    ),
    # Weak by construction: TIP is a mechanism, not a field.
    "nsf_tip": (
        "oa_field_14",  # Business, Management and Accounting
        "oa_field_22",  # Engineering
    ),
}

# Directorates whose mapping is a convenience rather than a real equivalence.
# Any analysis that leans on these should say so.
WEAK_MAPPINGS: FrozenSet[str] = frozenset({"nsf_tip", "nsf_edu"})

# OpenAlex fields with no NSF directorate. Kept explicit so that the coverage
# gap is asserted by a test rather than rediscovered later.
UNMAPPED_OPENALEX_FIELDS: FrozenSet[str] = frozenset({
    "oa_field_27",  # Medicine
    "oa_field_29",  # Nursing
    "oa_field_30",  # Pharmacology, Toxicology and Pharmaceutics
    "oa_field_34",  # Veterinary
    "oa_field_35",  # Dentistry
    "oa_field_36",  # Health Professions
})


def openalex_fields_for(directorate: str) -> List[str]:
    """Fields a directorate maps onto, best match first. Empty if unknown."""
    return list(NSF_TO_OPENALEX.get(directorate, ()))


def primary_openalex_field(directorate: str) -> Optional[str]:
    """The single best-matching field, or None."""
    fields = NSF_TO_OPENALEX.get(directorate)
    return fields[0] if fields else None


def directorates_for(openalex_field: str) -> List[str]:
    """Reverse lookup: directorates that map onto a field, sorted."""
    return sorted(
        directorate
        for directorate, fields in NSF_TO_OPENALEX.items()
        if openalex_field in fields
    )


def is_weak(directorate: str) -> bool:
    """Whether this directorate's mapping is a convenience, not an equivalence."""
    return directorate in WEAK_MAPPINGS


def coverage_report() -> Dict[str, object]:
    """Summarise what the crosswalk does and does not reach."""
    mapped = {f for fields in NSF_TO_OPENALEX.values() for f in fields}
    shared = sorted(f for f in mapped if len(directorates_for(f)) > 1)
    return {
        "directorates": len(NSF_TO_OPENALEX),
        "openalex_fields_mapped": len(mapped),
        "openalex_fields_unmapped": len(UNMAPPED_OPENALEX_FIELDS),
        "fields_shared_by_multiple_directorates": shared,
        "weak_mappings": sorted(WEAK_MAPPINGS),
    }
