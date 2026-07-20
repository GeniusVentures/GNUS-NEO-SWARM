"""GNUS-POC quantization — FP4 binary export for C++ engine.

Provides:
- FP4Exporter: SGFP4 v1 fixed 64x64 and v2 adaptive quadtree export
- ManifestBuilder: provenance manifest generation with SHA256 hashing
- LaplacianWeightedError: encode-side Laplacian pyramid error analysis
- QuadtreeEncoder: adaptive block-size selection via quadtree recursion
- decode_v1 / decode_v2: independent reference decoder (normative semantics)
"""

from quantize.fp4_exporter import FP4Exporter
from quantize.laplacian import LaplacianWeightedError
from quantize.manifest import ManifestBuilder
from quantize.quadtree import QuadtreeEncoder
from quantize.sgfp4_decoder import decode_v1, decode_v2

__all__ = [
    "FP4Exporter",
    "LaplacianWeightedError",
    "ManifestBuilder",
    "QuadtreeEncoder",
    "decode_v1",
    "decode_v2",
]
