"""
Ray-based shared memory implementation for VWAP Prediction
Provides distributed object store for DataFrame sharing across processes
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Callable, Any
import logging
import time
import pickle

logger = logging.getLogger(__name__)


class RaySharedMemory:
    """
    High-performance shared memory for DataFrames using Ray's object store
    Uses Ray's distributed object store for zero-copy access across processes
    """

    def __init__(self, namespace: str = "vwap_prediction", redis_password: str = None, ray_address: str = "auto"):
        """
        Initialize Ray shared memory

        Args:
            namespace: Ray namespace for isolation (default: "vwap_prediction")
            redis_password: Optional Redis password for Ray cluster
            ray_address: Ray address to connect to (default: "auto" tries to find existing, use None for local)
        """
        try:
            import ray
        except ImportError:
            raise ImportError(
                "Ray is not installed. Install with: pip install ray"
            )

        self.namespace = namespace

        # Initialize Ray if not already running
        if not ray.is_initialized():
            init_kwargs = {
                "namespace": namespace,
                "ignore_reinit_error": True,
            }

            # Try to connect to existing Ray instance first
            if ray_address == "auto":
                try:
                    # Try to connect to existing Ray cluster
                    init_kwargs["address"] = "auto"
                    ray.init(**init_kwargs)
                    logger.info(f"Connected to existing Ray instance with namespace: {namespace}")
                except:
                    # No existing cluster, start local
                    init_kwargs.pop("address", None)
                    ray.init(**init_kwargs)
                    logger.info(f"Started local Ray instance with namespace: {namespace}")
            elif ray_address:
                init_kwargs["address"] = ray_address
                if redis_password:
                    init_kwargs["redis_password"] = redis_password
                ray.init(**init_kwargs)
                logger.info(f"Connected to Ray at {ray_address} with namespace: {namespace}")
            else:
                # Start local Ray instance
                if redis_password:
                    init_kwargs["redis_password"] = redis_password
                ray.init(**init_kwargs)
                logger.info(f"Started local Ray instance with namespace: {namespace}")
        else:
            logger.info(f"Ray already initialized (namespace: {namespace})")

        # Use a simple dict stored in Ray's object store to map keys to ObjectRefs
        # This allows key-based retrieval similar to Arrow implementation
        try:
            self._key_store = ray.get_actor("vwap_ray_key_store")
            logger.info("Connected to existing Ray key store")
        except ValueError:
            # Key store doesn't exist, create it
            @ray.remote
            class KeyStore:
                def __init__(self):
                    self.keys = {}

                def put(self, key: str, data):
                    """Store data directly (Ray handles object refs internally)"""
                    self.keys[key] = data

                def get(self, key: str):
                    """Get data directly"""
                    return self.keys.get(key)

                def exists(self, key: str):
                    return key in self.keys

                def delete(self, key: str):
                    if key in self.keys:
                        del self.keys[key]
                        return True
                    return False

                def list_keys(self):
                    return list(self.keys.keys())

            self._key_store = KeyStore.options(name="vwap_ray_key_store", lifetime="detached").remote()
            logger.info("Created new Ray key store")

    def save(self, df: pd.DataFrame, key: str) -> str:
        """
        Save DataFrame to Ray's object store

        Args:
            df: DataFrame to save
            key: Unique identifier for the data

        Returns:
            Key identifier
        """
        import ray

        # Store DataFrame in KeyStore actor (Ray handles object storage)
        ray.get(self._key_store.put.remote(key, df))

        logger.debug(f"Saved {len(df)} rows x {len(df.columns)} cols to Ray with key: {key}")
        return key

    def load(self, key: str) -> pd.DataFrame:
        """
        Load DataFrame from Ray's object store

        Args:
            key: Unique identifier for the data

        Returns:
            DataFrame (potentially zero-copy if in same process)
        """
        import ray

        # Get DataFrame from KeyStore actor
        df = ray.get(self._key_store.get.remote(key))

        if df is None:
            raise KeyError(f"Data with key '{key}' not found in Ray object store")

        logger.debug(f"Loaded {len(df)} rows x {len(df.columns)} cols from Ray with key: {key}")
        return df

    def exists(self, key: str) -> bool:
        """Check if data exists"""
        import ray
        return ray.get(self._key_store.exists.remote(key))

    def delete(self, key: str):
        """Delete data"""
        import ray
        deleted = ray.get(self._key_store.delete.remote(key))
        if deleted:
            logger.debug(f"Deleted key: {key}")

    def list_keys(self) -> list:
        """List all available keys"""
        import ray
        return ray.get(self._key_store.list_keys.remote())

    def cleanup(self):
        """Cleanup - not needed for Ray as it has automatic garbage collection"""
        logger.info("Ray object store uses automatic garbage collection")
        pass

    def shutdown(self):
        """Shutdown Ray (use with caution - affects all Ray users)"""
        import ray
        if ray.is_initialized():
            ray.shutdown()
            logger.info("Ray shutdown")


def gen_ray_functions(
    namespace: str = "vwap_prediction",
    redis_password: str = None,
) -> Tuple[Callable, Callable, Callable, Callable]:
    """
    Generate Ray-based shared memory functions

    Returns:
        Tuple of (ray_put, ray_get, ray_save, ray_load) functions
    """
    ray_sm = RaySharedMemory(namespace=namespace, redis_password=redis_password)

    def ray_put(obj: Any) -> str:
        """Put object (generates unique key)"""
        key = f"obj_{int(time.time() * 1000000)}"
        if isinstance(obj, pd.DataFrame):
            ray_sm.save(obj, key)
        else:
            # For non-DataFrame objects, wrap in DataFrame
            df = pd.DataFrame({"data": [obj]})
            ray_sm.save(df, key)
        return key

    def ray_get(key: str) -> Any:
        """Get object by key"""
        df = ray_sm.load(key)
        if len(df) == 1 and "data" in df.columns:
            # Was a non-DataFrame object
            return df["data"].iloc[0]
        return df

    def ray_save(key: str, obj: Any) -> str:
        """Save with specific key"""
        if isinstance(obj, pd.DataFrame):
            ray_sm.save(obj, key)
        else:
            # For non-DataFrame objects, wrap in DataFrame
            df = pd.DataFrame({"data": [obj]})
            ray_sm.save(df, key)
        return key

    def ray_load(key: str) -> Any:
        """Load with specific key"""
        try:
            df = ray_sm.load(key)
            if len(df) == 1 and "data" in df.columns:
                # Was a non-DataFrame object
                return df["data"].iloc[0]
            return df
        except KeyError:
            logger.warning(f"Key '{key}' not found in Ray shared memory")
            return None

    return ray_put, ray_get, ray_save, ray_load
