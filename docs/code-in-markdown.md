
# Q:
run_test.pyPythonquant_pyramid_v2.pyPythonquant_pyramid.pyPythonfp4.pyPythonquant_baseline.pyPythonpyramids.pyPythonoutput the files here in markdown
# A:
Here are all the uploaded files rendered **fully in Markdown** exactly as requested.



## run_test.py


```python
# run_test.py
import numpy as np
import torch
import torch.nn.functional as F
from quant_pyramid_v2 import QuantPyramid

def test_quant_pyramid():
    B, C, H, W = 1, 3, 64, 64
    x = torch.rand(B, C, H, W).cuda()

    qp = QuantPyramid(
        num_levels=3,
        base_channels=16,
        codebook_size=256,
        embedding_dim=16,
        use_fp4=True
    ).cuda()

    y, aux = qp(x)
    print("Output shape:", y.shape)
    for k, v in aux.items():
        print(k, v.shape if torch.is_tensor(v) else v)

if __name__ == "__main__":
    test_quant_pyramid()

```


## quant_pyramid_v2.py


```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from fp4 import FP4Quantizer
from quant_baseline import VectorQuantizerEMA

class DownsampleBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, kernel_size=4, stride=2, padding=1)

    def forward(self, x):
        return F.relu(self.conv(x))


class UpsampleBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.ConvTranspose2d(in_ch, out_ch, kernel_size=4, stride=2, padding=1)

    def forward(self, x):
        return F.relu(self.conv(x))


class QuantPyramid(nn.Module):
    def __init__(self, num_levels, base_channels, codebook_size, embedding_dim, use_fp4=True):
        super().__init__()
        self.num_levels = num_levels
        self.use_fp4 = use_fp4

        self.down = nn.ModuleList()
        self.up = nn.ModuleList()
        self.quantizers = nn.ModuleList()

        in_ch = 3
        for i in range(num_levels):
            out_ch = base_channels * (2 ** i)
            self.down.append(DownsampleBlock(in_ch, out_ch))
            self.quantizers.append(VectorQuantizerEMA(codebook_size, embedding_dim))
            in_ch = out_ch

        for i in range(num_levels - 1, -1, -1):
            out_ch = base_channels * (2 ** max(i - 1, 0))
            self.up.append(UpsampleBlock(in_ch, out_ch))
            in_ch = out_ch

        self.to_embed = nn.Conv2d(base_channels * (2 ** (num_levels - 1)), embedding_dim, 1)
        self.from_embed = nn.Conv2d(embedding_dim, base_channels, 1)

        self.fp4 = FP4Quantizer() if use_fp4 else None

    def forward(self, x):
        downs = []
        h = x

        for d in self.down:
            h = d(h)
            downs.append(h)

        emb = self.to_embed(downs[-1])
        q_emb, q_info = self.quantizers[-1](emb)

        if self.use_fp4:
            q_emb = self.fp4.quantize(q_emb)

        up_h = self.from_embed(q_emb)

        for i, u in enumerate(self.up):
            up_h = u(up_h)
            if i &lt; len(downs) - 1:
                up_h = up_h + downs[-2 - i]

        return up_h, {"quant": q_info, "fp4_used": self.use_fp4}

```


## quant_pyramid.py


```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class QuantPyramid(nn.Module):
    def __init__(self, in_channels=3, hidden_dim=32, num_levels=3):
        super().__init__()
        self.enc_blocks = nn.ModuleList()
        self.dec_blocks = nn.ModuleList()

        ch = in_channels
        for _ in range(num_levels):
            self.enc_blocks.append(nn.Conv2d(ch, hidden_dim, 3, stride=2, padding=1))
            ch = hidden_dim

        for _ in range(num_levels):
            self.dec_blocks.append(nn.ConvTranspose2d(ch, hidden_dim, 4, 2, 1))
            ch = hidden_dim

        self.out = nn.Conv2d(hidden_dim, in_channels, 1)

    def forward(self, x):
        stack = []
        h = x
        for blk in self.enc_blocks:
            h = F.relu(blk(h))
            stack.append(h)

        for i, blk in enumerate(self.dec_blocks):
            h = F.relu(blk(h))
            if i &lt; len(stack):
                h = h + stack[-1 - i]

        return self.out(h)

```


## fp4.py


```python
import torch
import torch.nn as nn

class FP4Quantizer(nn.Module):
    def __init__(self):
        super().__init__()

    def quantize(self, x):
        scale = torch.max(torch.abs(x))
        q = torch.clamp((x / scale) * 7, -8, 7)
        q_round = torch.round(q)
        return q_round * (scale / 7)

```


## quant_baseline.py


```python
import torch
import torch.nn as nn
import torch.nn.functional as F

class VectorQuantizerEMA(nn.Module):
    def __init__(self, num_embeddings, embedding_dim, decay=0.99, eps=1e-5):
        super().__init__()

        self.embedding = nn.Embedding(num_embeddings, embedding_dim)
        self.decay = decay
        self.eps = eps

        self.register_buffer("cluster_size", torch.zeros(num_embeddings))
        self.register_buffer("embed_avg", torch.zeros(num_embeddings, embedding_dim))

    def forward(self, z):
        B, C, H, W = z.shape
        flat = z.permute(0, 2, 3, 1).reshape(-1, C)

        dist = (
            flat.pow(2).sum(1, keepdim=True)
            - 2 * flat @ self.embedding.weight.t()
            + self.embedding.weight.pow(2).sum(1)
        )

        ids = torch.argmin(dist, dim=1)
        quant = self.embedding(ids).view(B, H, W, C).permute(0, 3, 1, 2)

        if self.training:
            one_hot = F.one_hot(ids, self.embedding.num_embeddings).float()
            self.cluster_size.mul_(self.decay).add_(one_hot.sum(0), alpha=1 - self.decay)

            embed_sum = one_hot.t() @ flat
            self.embed_avg.mul_(self.decay).add_(embed_sum, alpha=1 - self.decay)

            n = self.cluster_size.sum()
            cluster_size = (self.cluster_size + self.eps) / (n + self.embedding.num_embeddings * self.eps)
            self.embedding.weight.data.copy_(self.embed_avg / cluster_size.unsqueeze(1))

        return quant, {"ids": ids.view(B, H, W)}

```


## pyramids.py


```python
import torch
import torch.nn.functional as F

def gaussian_kernel(kernel_size=5, sigma=1.0, channels=3):
    ax = torch.arange(kernel_size) - kernel_size // 2
    xx, yy = torch.meshgrid(ax, ax, indexing="ij")
    kernel = torch.exp(-(xx**2 + yy**2) / (2 * sigma**2))
    kernel = kernel / kernel.sum()
    return kernel.expand(channels, 1, kernel_size, kernel_size)

def gaussian_blur(x, kernel_size=5, sigma=1.0):
    C = x.shape[1]
    kernel = gaussian_kernel(kernel_size, sigma, C).to(x.device)
    return F.conv2d(x, kernel, padding=kernel_size // 2, groups=C)

def downsample(x):
    return F.avg_pool2d(x, 2)

def upsample(x):
    return F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)

def build_laplacian_pyramid(x, levels=3):
    gaussian_pyr = [x]
    for _ in range(levels):
        gaussian_pyr.append(downsample(gaussian_blur(gaussian_pyr[-1])))

    laplacian_pyr = []
    for i in range(levels):
        up = upsample(gaussian_pyr[i + 1])
        laplacian = gaussian_pyr[i] - up
        laplacian_pyr.append(laplacian)

    laplacian_pyr.append(gaussian_pyr[-1])
    return laplacian_pyr

def reconstruct_laplacian_pyramid(pyr):
    current = pyr[-1]
    for i in reversed(range(len(pyr) - 1)):
        current = upsample(current) + pyr[i]
    return current

```


If you'd like these bundled into a downloadable ZIP, or want documentation or refactoring, just tell me.