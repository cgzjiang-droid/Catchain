"""Public domain models for CATchain."""

from catchain.domain.common import Sha256
from catchain.domain.documents import DocumentType, DocumentVersion, Registry, SourceDocument
from catchain.domain.evaluation import DimensionEvaluation, EvaluationResult
from catchain.domain.evidence import EvidenceRef
from catchain.domain.extraction import FieldObservation, ProjectExtraction
from catchain.domain.gold import GoldDataset, GoldFieldLabel, GoldSample
from catchain.domain.parsing import ParsedDocument, ParsedPage, TextQuality
from catchain.domain.pipeline import PipelineRun, PipelineStage, RunStatus

__all__ = [
    "DocumentType",
    "DocumentVersion",
    "DimensionEvaluation",
    "EvidenceRef",
    "EvaluationResult",
    "FieldObservation",
    "GoldFieldLabel",
    "GoldDataset",
    "GoldSample",
    "ParsedDocument",
    "ParsedPage",
    "PipelineRun",
    "PipelineStage",
    "ProjectExtraction",
    "Registry",
    "RunStatus",
    "Sha256",
    "SourceDocument",
    "TextQuality",
]
