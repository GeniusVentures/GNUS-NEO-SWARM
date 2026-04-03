# run_test.py
import numpy as np

from pyramids import gaussian_pyramid, laplacian_pyramid, reconstruct
from quant_baseline import baseline_quantize
from quant_pyramid import quantize_laplacian_pyramid
from quant_pyramid_v2 import quantize_laplacian_pyramid_v2



def main():
    print("===== GNUS PQ4 MVP Test =====")

    # Generate synthetic weight matrix
    W = np.random.randn(512, 512).astype(np.float32)
    print("Generated random 512x512 weights.")

    # 1. Pyramid Sanity Test
    print("\n--- Pyramid Reconstruction Test ---")
    gp = gaussian_pyramid(W, levels=3)
    lp = laplacian_pyramid(gp)
    W_recon = reconstruct(lp)

    recon_err = np.abs(W - W_recon).mean()
    print("Reconstruction mean error:", f"{recon_err:.6e}")

    # 2. Baseline FP4 Quantization
    print("\n--- Baseline FP4 Quantization ---")
    Wq_base, scales_base = baseline_quantize(W)
    err_base = np.abs(W - Wq_base).mean()
    print("Baseline FP4 quantization error (mean abs):", f"{err_base:.6f}")

    # 3. Pyramid-based FP4 Quantization (MVP)
    print("\n--- Pyramid FP4 Quantization (Laplacian, global per-level scale) ---")
    Wq_pyr, scales_pyr = quantize_laplacian_pyramid(W, levels=3)
    err_pyr = np.abs(W - Wq_pyr).mean()
    print("Pyramid FP4 quantization error (mean abs):", f"{err_pyr:.6f}")

    # 4. Pyramid FP4 Version 2 (per-row quantization)
    print("\n--- Pyramid FP4 Quantization V2 (per-row Laplacian) ---")
    Wq_pyr2, scales_pyr2 = quantize_laplacian_pyramid_v2(W, levels=3)
    err_pyr2 = np.abs(W - Wq_pyr2).mean()
    print("Pyramid V2 FP4 quantization error:", f"{err_pyr2:.6f}")

    improve2 = err_base - err_pyr2
    print("Error difference (baseline - pyramid V2):", f"{improve2:.6f}")
    if improve2 > 0:
        print("✅ Pyramid V2 beat baseline!")
    else:
        print("⚠️ Pyramid V2 still worse — more refinement needed.")

    # Optional: relative improvement (may be negative initially)
    improvement = err_base - err_pyr
    print("\nError difference (baseline - pyramid):", f"{improvement:.6f}")
    if improvement > 0:
        print("✅ Pyramid quantization is better (lower error).")
    else:
        print("⚠️ Pyramid quantization is worse (for this MVP config) — needs tuning.")

    print("\nAll done.")


if __name__ == "__main__":
    main()
