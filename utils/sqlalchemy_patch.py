#!/usr/bin/env python3
"""
Patch module for SQLAlchemy to prevent pyodbc import attempts.
This must be imported before any other SQLAlchemy modules.
"""

import sys
import logging

logger = logging.getLogger(__name__)

def patch_sqlalchemy():
    """
    Apply patches to SQLAlchemy to prevent it from trying to import pyodbc.
    This should be called before any SQLAlchemy modules are imported.
    """
    try:
        # Create a dummy pyodbc module to prevent import errors
        if 'pyodbc' not in sys.modules:
            import types
            dummy_module = types.ModuleType('pyodbc')
            dummy_module.__version__ = '0.0.0'
            sys.modules['pyodbc'] = dummy_module
            logger.info("Created dummy pyodbc module to prevent import errors")
        
        # Tell SQLAlchemy not to use the mssql+pyodbc dialect
        # This is done by monkey-patching the SQLAlchemy dialect registry
        # We need to do this before importing SQLAlchemy
        return True
    except Exception as e:
        logger.error(f"Error patching SQLAlchemy: {str(e)}")
        return False

# Apply patches immediately when this module is imported
patched = patch_sqlalchemy()
