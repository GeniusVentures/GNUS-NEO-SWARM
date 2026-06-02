"""
Common Pile Niche Discovery Script
Analyzes Common Pile dataset to identify viable niches for GNUS.ai specialists

This script:
1. Streams Common Pile to avoid memory issues
2. Extracts topics using TF-IDF + clustering
3. Identifies niches with sufficient data (>10k samples recommended)
4. Outputs niche recommendations with sample texts
"""

import os
import json
import numpy as np
from collections import Counter, defaultdict
from datasets import load_dataset
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
import re
from typing import List, Dict, Tuple
import pickle

# Configuration
SAMPLE_SIZE = 50000  # Number of documents to analyze (balance speed vs coverage)
N_CLUSTERS = 20      # Initial cluster count (will identify top 5 as niches)
MIN_NICHE_SIZE = 5000  # Minimum samples per niche for viable specialist
MAX_FEATURES = 5000  # TF-IDF vocabulary size
RANDOM_SEED = 42

# Output paths
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = str(PROJECT_ROOT / "data" / "analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text: str) -> str:
    """Clean and normalize text for analysis"""
    if not text or len(text) < 100:  # Skip very short texts
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http\S+|www\.\S+', '', text)
    
    # Keep only ASCII printable (Common Pile is mostly English)
    text = ''.join(char for char in text if 32 <= ord(char) <= 126 or char in '\n\t')
    
    return text.strip()

def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """Extract potential domain keywords from text"""
    # Simple keyword extraction: capitalized words, technical terms
    words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)  # Proper nouns
    technical = re.findall(r'\b[a-z]+(?:tion|ology|ics|ism|ance|ence)\b', text.lower())  # Technical suffixes
    
    return list(set(words[:top_n] + technical[:top_n]))

def load_and_sample_common_pile(sample_size: int = SAMPLE_SIZE) -> Tuple[List[str], List[Dict]]:
    """
    Load Common Pile and extract representative sample
    Returns: (texts, metadata)
    """
    print(f"Loading Common Pile (streaming mode, target {sample_size} samples)...")
    
    try:
        # Try filtered version first (cleaner)
        dataset = load_dataset(
            "monology/pile-uncopyrighted",  # Alternative: "common-pile/common-pile-v0.1-filtered"
            split="train",
            streaming=True,
            trust_remote_code=True
        )
    except Exception as e:
        print(f"Note: Using alternative dataset due to: {e}")
        # Fallback to a known-working pile subset
        dataset = load_dataset(
            "EleutherAI/pile",
            split="train",
            streaming=True,
            trust_remote_code=True
        )
    
    texts = []
    metadata = []
    
    print("Sampling documents...")
    for i, example in enumerate(dataset):
        if i >= sample_size:
            break
        
        if i % 5000 == 0:
            print(f"  Processed {i}/{sample_size} documents...")
        
        # Extract text (field name varies by dataset version)
        text = example.get('text', example.get('content', ''))
        cleaned = clean_text(text)
        
        if len(cleaned) >= 100:  # Only keep substantial texts
            texts.append(cleaned)
            metadata.append({
                'source': example.get('meta', {}).get('pile_set_name', 'unknown'),
                'length': len(cleaned),
                'keywords': extract_keywords(cleaned)
            })
    
    print(f"Collected {len(texts)} valid documents")
    return texts, metadata

def cluster_documents(texts: List[str], n_clusters: int = N_CLUSTERS) -> Tuple[np.ndarray, TfidfVectorizer, MiniBatchKMeans]:
    """
    Cluster documents using TF-IDF + MiniBatchKMeans
    Returns: (cluster_labels, vectorizer, clustering_model)
    """
    print(f"\nVectorizing texts (max {MAX_FEATURES} features)...")
    
    vectorizer = TfidfVectorizer(
        max_features=MAX_FEATURES,
        min_df=5,  # Word must appear in at least 5 docs
        max_df=0.7,  # Ignore words in >70% of docs (too common)
        stop_words='english',
        ngram_range=(1, 2)  # Unigrams and bigrams
    )
    
    tfidf_matrix = vectorizer.fit_transform(texts)
    print(f"TF-IDF matrix shape: {tfidf_matrix.shape}")
    
    # Dimensionality reduction for faster clustering
    print("Reducing dimensions with SVD...")
    svd = TruncatedSVD(n_components=min(100, tfidf_matrix.shape[1] - 1), random_state=RANDOM_SEED)
    reduced_matrix = svd.fit_transform(tfidf_matrix)
    print(f"Explained variance: {svd.explained_variance_ratio_.sum():.2%}")
    
    # Cluster
    print(f"Clustering into {n_clusters} groups...")
    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=RANDOM_SEED,
        batch_size=1000,
        max_iter=100
    )
    labels = kmeans.fit_predict(reduced_matrix)
    
    print(f"Clustering complete. Cluster sizes:")
    cluster_counts = Counter(labels)
    for cluster_id, count in sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  Cluster {cluster_id}: {count} documents ({count/len(labels)*100:.1f}%)")
    
    return labels, vectorizer, kmeans

def analyze_clusters(texts: List[str], labels: np.ndarray, metadata: List[Dict], vectorizer: TfidfVectorizer) -> List[Dict]:
    """
    Analyze each cluster to identify niche characteristics
    Returns: List of niche descriptions
    """
    print("\nAnalyzing clusters to identify niches...")
    
    niches = []
    feature_names = vectorizer.get_feature_names_out()
    tfidf_matrix = vectorizer.transform(texts)
    
    for cluster_id in range(labels.max() + 1):
        cluster_mask = labels == cluster_id
        cluster_size = cluster_mask.sum()
        
        if cluster_size < MIN_NICHE_SIZE:
            continue  # Skip small clusters
        
        # Get cluster documents
        cluster_texts = [texts[i] for i in np.where(cluster_mask)[0]]
        cluster_meta = [metadata[i] for i in np.where(cluster_mask)[0]]
        
        # Extract top TF-IDF terms for this cluster
        cluster_tfidf = tfidf_matrix[cluster_mask].mean(axis=0).A1
        top_indices = cluster_tfidf.argsort()[-20:][::-1]
        top_terms = [feature_names[i] for i in top_indices]
        
        # Aggregate keywords from metadata
        all_keywords = []
        for meta in cluster_meta:
            all_keywords.extend(meta['keywords'])
        keyword_counts = Counter(all_keywords).most_common(15)
        
        # Source distribution
        sources = Counter([meta['source'] for meta in cluster_meta])
        
        # Sample texts
        sample_indices = np.random.choice(len(cluster_texts), min(5, len(cluster_texts)), replace=False)
        samples = [cluster_texts[i][:500] + "..." for i in sample_indices]
        
        niche = {
            'cluster_id': int(cluster_id),
            'size': int(cluster_size),
            'percentage': float(cluster_size / len(texts) * 100),
            'top_terms': top_terms,
            'top_keywords': [kw for kw, _ in keyword_counts],
            'sources': dict(sources.most_common(5)),
            'avg_length': int(np.mean([meta['length'] for meta in cluster_meta])),
            'samples': samples
        }
        
        niches.append(niche)
    
    # Sort by size
    niches.sort(key=lambda x: x['size'], reverse=True)
    
    return niches

def suggest_niche_names(niches: List[Dict]) -> List[Dict]:
    """
    Suggest human-readable names for niches based on top terms
    """
    print("\nSuggesting niche names...")
    
    for niche in niches:
        # Heuristic naming based on top terms
        terms = niche['top_terms'][:5]
        keywords = niche['top_keywords'][:5]
        
        # Look for domain indicators
        all_tokens = ' '.join(terms + keywords).lower()
        
        # Domain detection patterns
        domains = {
            'science': ['research', 'study', 'scientific', 'experiment', 'theory', 'hypothesis'],
            'mathematics': ['equation', 'theorem', 'proof', 'mathematics', 'calculus', 'algebra'],
            'history': ['century', 'war', 'historical', 'ancient', 'period', 'empire'],
            'literature': ['novel', 'poem', 'author', 'literary', 'poetry', 'prose'],
            'law': ['court', 'legal', 'law', 'statute', 'judge', 'case'],
            'medicine': ['patient', 'medical', 'disease', 'treatment', 'clinical', 'health'],
            'technology': ['software', 'computer', 'system', 'algorithm', 'programming', 'data'],
            'philosophy': ['philosophy', 'argument', 'ethics', 'moral', 'philosophical', 'logic'],
            'economics': ['economic', 'market', 'trade', 'financial', 'economy', 'price'],
            'geography': ['region', 'area', 'located', 'geographic', 'climate', 'population']
        }
        
        detected_domains = []
        for domain, indicators in domains.items():
            if any(indicator in all_tokens for indicator in indicators):
                detected_domains.append(domain)
        
        # Generate suggested name
        if detected_domains:
            suggested_name = detected_domains[0].title()
        else:
            # Fallback: use top 2 terms
            suggested_name = f"{terms[0].title()}-{terms[1].title()}"
        
        niche['suggested_name'] = suggested_name
        niche['detected_domains'] = detected_domains
    
    return niches

def save_analysis(niches: List[Dict], texts: List[str], labels: np.ndarray):
    """Save analysis results for later use"""
    
    # Save niche descriptions
    with open(f"{OUTPUT_DIR}/niches.json", 'w') as f:
        json.dump(niches, f, indent=2)
    
    # Save cluster assignments for dataset preparation
    cluster_map = defaultdict(list)
    for idx, label in enumerate(labels):
        cluster_map[int(label)].append(idx)
    
    with open(f"{OUTPUT_DIR}/cluster_map.pkl", 'wb') as f:
        pickle.dump(dict(cluster_map), f)
    
    print(f"\nResults saved to {OUTPUT_DIR}/")

def print_recommendations(niches: List[Dict]):
    """Print top niche recommendations"""
    
    print("\n" + "="*80)
    print("TOP NICHE RECOMMENDATIONS FOR GNUS.AI SPECIALISTS")
    print("="*80)
    
    top_niches = niches[:5]
    
    for i, niche in enumerate(top_niches, 1):
        print(f"\n--- NICHE {i}: {niche['suggested_name']} ---")
        print(f"Size: {niche['size']:,} documents ({niche['percentage']:.1f}%)")
        print(f"Avg Length: {niche['avg_length']:,} chars")
        print(f"Detected Domains: {', '.join(niche['detected_domains']) if niche['detected_domains'] else 'General'}")
        print(f"\nTop Terms: {', '.join(niche['top_terms'][:10])}")
        print(f"Top Keywords: {', '.join(niche['top_keywords'][:10])}")
        print(f"\nSample Text:")
        print(f"  {niche['samples'][0][:300]}...")
        print()
    
    print("="*80)
    print(f"\nRECOMMENDATION: Select 3-5 niches from above for specialist training.")
    print(f"Prioritize niches with:")
    print(f"  • Size > {MIN_NICHE_SIZE:,} documents")
    print(f"  • Clear domain focus (check detected_domains)")
    print(f"  • Distinct top terms (minimal overlap with other niches)")
    print(f"\nNext step: Run prepare_datasets.py with selected niche IDs")

def main():
    """Main execution"""
    print("GNUS.AI Common Pile Niche Discovery")
    print("="*80)
    
    # Load data
    texts, metadata = load_and_sample_common_pile(SAMPLE_SIZE)
    
    if len(texts) < 1000:
        print("ERROR: Insufficient data loaded. Check dataset availability.")
        return
    
    # Cluster
    labels, vectorizer, kmeans = cluster_documents(texts, N_CLUSTERS)
    
    # Analyze
    niches = analyze_clusters(texts, labels, metadata, vectorizer)
    
    # Name suggestions
    niches = suggest_niche_names(niches)
    
    # Save
    save_analysis(niches, texts, labels)
    
    # Print recommendations
    print_recommendations(niches)
    
    print(f"\n✓ Analysis complete! Check {OUTPUT_DIR}/niches.json for full details.")

if __name__ == "__main__":
    main()
