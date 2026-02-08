"""
Address book management for saving contact aliases and transfer history.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Data file path
DATA_DIR = Path(__file__).parent.parent / "data"
CONTACTS_FILE = DATA_DIR / "contacts.json"

def _ensure_data_dir():
    """Create data directory if not exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def _load_contacts() -> Dict:
    """Load contacts from JSON file."""
    _ensure_data_dir()
    if CONTACTS_FILE.exists():
        try:
            with open(CONTACTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def _save_contacts(contacts: Dict):
    """Save contacts to JSON file."""
    _ensure_data_dir()
    with open(CONTACTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(contacts, f, ensure_ascii=False, indent=2)

def save_contact(
    address: str,
    alias: str = None,
    increment_count: bool = True
) -> Dict:
    """
    Save or update a contact in address book.
    
    Args:
        address: TRON address
        alias: Optional alias/nickname for this address
        increment_count: Whether to increment transfer count
        
    Returns:
        Updated contact info
    """
    contacts = _load_contacts()
    
    now = datetime.now().isoformat()
    
    if address in contacts:
        # Update existing contact
        contact = contacts[address]
        if alias:
            contact['alias'] = alias
        if increment_count:
            contact['transfer_count'] = contact.get('transfer_count', 0) + 1
            contact['last_transfer'] = now
    else:
        # Create new contact
        contact = {
            'alias': alias or None,
            'transfer_count': 1 if increment_count else 0,
            'first_seen': now,
            'last_transfer': now if increment_count else None
        }
        contacts[address] = contact
    
    _save_contacts(contacts)
    return contact

def get_contact_alias(address: str) -> Optional[str]:
    """Get alias for an address, or None if not found."""
    contacts = _load_contacts()
    contact = contacts.get(address)
    return contact.get('alias') if contact else None

def get_contact_info(address: str) -> Optional[Dict]:
    """Get full contact info for an address."""
    contacts = _load_contacts()
    return contacts.get(address)

def list_contacts(sort_by: str = "count") -> List[Dict]:
    """
    List all contacts.
    
    Args:
        sort_by: 'count' (most used), 'recent' (recently added), 'alpha' (alphabetical)
        
    Returns:
        List of contacts with address and info
    """
    contacts = _load_contacts()
    
    contact_list = [
        {
            'address': addr,
            **info
        }
        for addr, info in contacts.items()
    ]
    
    # Sort
    if sort_by == "count":
        contact_list.sort(key=lambda x: x.get('transfer_count', 0), reverse=True)
    elif sort_by == "recent":
        contact_list.sort(key=lambda x: x.get('first_seen', ''), reverse=True)
    elif sort_by == "alpha":
        contact_list.sort(key=lambda x: x.get('alias', x['address']).lower())
    
    return contact_list

def search_contacts(query: str) -> List[Dict]:
    """
    Search contacts by alias or address.
    
    Args:
        query: Search string (case-insensitive)
        
    Returns:
        List of matching contacts
    """
    contacts = _load_contacts()
    query_lower = query.lower()
    
    results = []
    for addr, info in contacts.items():
        alias = info.get('alias', '')
        if query_lower in addr.lower() or (alias and query_lower in alias.lower()):
            results.append({
                'address': addr,
                **info
            })
    
    return results

def delete_contact(address: str) -> bool:
    """
    Delete a contact from address book.
    
    Returns:
        True if deleted, False if not found
    """
    contacts = _load_contacts()
    if address in contacts:
        del contacts[address]
        _save_contacts(contacts)
        return True
    return False

def get_contact_count() -> int:
    """Get total number of saved contacts."""
    contacts = _load_contacts()
    return len(contacts)
