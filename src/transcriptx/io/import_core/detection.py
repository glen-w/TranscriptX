from __future__ import annotations

from dataclasses import dataclass

from transcriptx.io.import_core.contracts import AdapterKind, DetectionClass

_KIND_ORDER = {
    AdapterKind.VENDOR: 3,
    AdapterKind.FAMILY: 2,
    AdapterKind.GENERIC: 1,
}

_CLASS_ORDER = {
    DetectionClass.REJECT: 0,
    DetectionClass.POSSIBLE: 1,
    DetectionClass.LIKELY: 2,
    DetectionClass.DEFINITIVE: 3,
}


@dataclass(frozen=True)
class SelectionPolicy:
    minimum_detection_class: DetectionClass = DetectionClass.LIKELY
    ambiguous_score_delta: float = 0.05


def kind_rank(kind: AdapterKind) -> int:
    return _KIND_ORDER[kind]


def class_rank(cls: DetectionClass) -> int:
    return _CLASS_ORDER[cls]
