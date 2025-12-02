import random
import numpy as np

class WorkloadGenerator:
    """Generates realistic workload patterns with Zipfian key distribution and Pareto request sizes."""
    
    def __init__(self, num_unique_keys=1000, zipf_alpha=1.8):
        self.num_unique_keys = num_unique_keys
        self.zipf_alpha = zipf_alpha  # Higher = more skewed (better for testing cache affinity)
        
        # Generate key pool (MORE keys = harder to cache)
        self.keys = [f"key_{i:04d}" for i in range(num_unique_keys)]
        
        # Pre-compute Zipfian probabilities
        # P(rank) = 1 / rank^alpha
        ranks = np.arange(1, num_unique_keys + 1)
        probabilities = 1.0 / np.power(ranks, zipf_alpha)
        self.probabilities = probabilities / np.sum(probabilities)
        
    def generate_request(self):
        """
        Generate a request tuple (key, size_kb).
        - Key: Follows Zipfian distribution (hotspots).
        - Size: Follows Pareto distribution (heavy tails).
        """
        # Select key (more skewed = few very popular keys)
        key = np.random.choice(self.keys, p=self.probabilities)
        
        # Generate size (Pareto distribution) - MORE EXTREME
        # Shape parameter (alpha) = 1.16 (80/20 rule approx)
        # Scale parameter (xm) = 1.0 KB (minimum size)
        size_kb = (np.random.pareto(1.16) + 1) * 1.0
        
        # Cap size but allow larger requests
        size_kb = min(size_kb, 5000.0)  # Up to 5MB
        
        return key, size_kb
