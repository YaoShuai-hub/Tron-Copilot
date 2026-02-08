"""
Malicious Address Detector

Checks TronScan tag database for malicious address labels.
"""

from .scripts.check_malicious import check_malicious_address

__all__ = ['check_malicious_address']
