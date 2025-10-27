from typing import List, Union, Any, Optional, Callable
from .vector_store import VectorStore, VectorStoreType
from .milvus import MilvusVectorStore
from .pinecone import PineconeVectorStore
from .chroma import ChromaVectorStore

#Here we import everything we need to call the different apis and interact with them behind wrapper

class VectorStoreClient:
    """Client for managing vector store connections and collections."""
    
    def __init__(
        self,
        store_type: Union[VectorStoreType, str],
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        environment: Optional[str] = None,
        path: Optional[str] = None,
        uri: Optional[str] = None,
        token: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Initialize the vector store client.
        
        Args:
            store_type: Type of vector store (milvus, pinecone, or chroma)
            api_key: API key for authentication (Pinecone)
            host: Host address (ChromaDB)
            port: Port number (ChromaDB)
            environment: Environment name (Pinecone)
            path: Local path for storage (ChromaDB)
            uri: Connection URI (Milvus)
            token: Authentication token (Milvus)
            **kwargs: Additional client-specific parameters
        """
        self.store_type = VectorStoreType(store_type) if isinstance(store_type, str) else store_type
        self.api_key = api_key
        self.host = host
        self.port = port
        self.environment = environment
        self.path = path
        self.uri = uri
        self.token = token
        self.kwargs = kwargs
    
    def create_collection(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
        dimension: int,
        **kwargs: Any
    ) -> VectorStore:
        """
        Create or connect to a collection in the vector store.
        
        Args:
            collection_name: Name of the collection to create/connect
            embedding_function: Function to convert text to embeddings
            dimension: Dimension of the embedding vectors
            **kwargs: Additional collection-specific parameters
            
        Returns:
            VectorStore instance for the specified collection
            
        Raises:
            ValueError: If store_type is not supported
        """
        if self.store_type == VectorStoreType.MILVUS:
            #Here we would do something like
            #collections = Milvus.collections(self.uri, self.token)
            #miluvus_object = collections.create_new(collection_name, dimension, metric)

            return MilvusVectorStore(
                collection_name=collection_name,
                embedding_function=embedding_function,
                client_object= None, #would be milvus_object
                dimension=dimension
            )
        elif self.store_type == VectorStoreType.PINECONE:
            return PineconeVectorStore(
                collection_name=collection_name,
                embedding_function=embedding_function,
                client_object = None, #would be pinecone_object
                dimension=dimension,
            )
        elif self.store_type == VectorStoreType.CHROMA:
            return ChromaVectorStore(
                collection_name=collection_name,
                embedding_function=embedding_function,
                client_object = None, #would be chroma_object
                dimension=dimension,
            )
        else:
            raise ValueError(f"Unsupported store type: {self.store_type}")
        
    def get_collection(
        self,
        collection_name: str,
        embedding_function: Callable[[List[str]], List[List[float]]],
        dimension: int,
        **kwargs: Any
    ) -> VectorStore:
        pass  # Similar to create_collection, but for existing collections 