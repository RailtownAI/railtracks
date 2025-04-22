

import os
import unittest
import numpy as np

# Assuming your class is in a file named embedding_manager.py
# Adjust the import statement as needed based on your actual project structure
from lorag.embedding_manager import EmbeddingManager


class TestEmbeddingManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """
        This method is called once before all tests run.
        We read the API key from an environment variable and initialize the
        EmbeddingManager.
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
        
        cls.manager = EmbeddingManager(api_key=api_key)

    def test_get_embedding(self):
        """
        Test getting a single embedding.
        """
        text = "Hello world!"
        embedding = self.manager.get_embedding(text)

        # Check that the embedding is a non-empty list of floats
        self.assertIsInstance(embedding, list, "Embedding should be a list.")
        self.assertGreater(len(embedding), 0, "Embedding should not be empty.")
        self.assertTrue(all(isinstance(x, float) for x in embedding),
                        "All elements in the embedding should be floats.")

    def test_get_embedding_batch(self):
        """
        Test getting embeddings for a batch of texts.
        Note: This test assumes the batch endpoint and logic in your code
        is properly supported. In many real scenarios, the "batch" approach
        may differ from what the standard OpenAI API offers.
        """
        texts = ["Hello world!", "How are you?", "OpenAI is amazing!"]
        embeddings_dict = self.manager.get_embedding_batch(texts)

        # We expect the returned dictionary to have as many items as input texts
        self.assertEqual(len(embeddings_dict), len(texts),
                         "Number of embeddings returned must match the number of texts.")

        for custom_id, embedding in embeddings_dict.items():
            self.assertIsInstance(embedding, list,
                                  f"Embedding for {custom_id} should be a list.")
            self.assertGreater(len(embedding), 0,
                               f"Embedding for {custom_id} should not be empty.")
            self.assertTrue(all(isinstance(x, float) for x in embedding),
                            f"All elements in the embedding for {custom_id} should be floats.")

    def test_calculate_similarity(self):
        """
        Test the cosine similarity calculation.
        We'll compute similarity between:
          - a vector and itself (should be ~1.0).
          - two distinct vectors (should be less than 1).
        """
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0]

        sim_same = self.manager.calculate_similarity(emb1, emb1)
        sim_diff = self.manager.calculate_similarity(emb1, emb2)

        # Similarity of a vector with itself should be 1 (or very close)
        self.assertAlmostEqual(sim_same, 1.0, delta=1e-6, 
                               msg="Similarity with itself should be close to 1.")
        # Emb1 and Emb2 are orthogonal
        self.assertAlmostEqual(sim_diff, 0.0, delta=1e-6,
                               msg="Similarity between orthogonal vectors should be close to 0.")

    def test_embedding_to_blob_and_back(self):
        """
        Test the serialization (to bytes blob) and deserialization (back to list of floats).
        """
        original_embedding = [0.123, 0.456, 0.789]
        blob = self.manager.embedding_to_blob(original_embedding)
        
        # Ensure blob is bytes
        self.assertIsInstance(blob, bytes, "Embedding should be converted to bytes.")
        self.assertGreater(len(blob), 0, "Blob should not be empty.")

        recovered_embedding = self.manager.blob_to_embedding(blob)

        self.assertIsInstance(recovered_embedding, list, 
                              "Recovered embedding should be a list.")
        # assert equal while allowing some floating point error
        for o, r in zip(original_embedding, recovered_embedding):
            self.assertAlmostEqual(o, r, delta=1e-5,
                                   msg="Recovered embedding should match original.")

if __name__ == "__main__":
    unittest.main()