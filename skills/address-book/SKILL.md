---
name: address-book
description: Manage address aliases and transfer history. Auto-create contact names from transfer memos, track transfer counts, and quickly access frequently-used addresses.
---

# Address Book Skill

## When to use this skill

Use this skill to:
- Save address aliases/nicknames for easy reference
- Auto-create contacts from transfer memos
- Track how many times you've sent to an address
- List frequently-used addresses
- Search for addresses by alias

## Features

### 1. 📝 Auto-Alias from Transfer Memo
When transferring with a memo, automatically save that memo as the address alias:
```
Transfer 100 TRX to TXXXabc... with memo "家人钱包"
→ Auto-saves: TXXXabc... = "家人钱包"
```

### 2. 📊 Transfer Count Tracking
Even without memo, tracks how many times sent to each address:
```
TYYYdef... : 5 transfers (no alias)
```

### 3. 🔍 Quick Lookup
Find addresses by alias:
```
"家人钱包" → TXXXabc...
```

### 4. 📋 List Contacts
View all saved addresses sorted by:
- Most frequently used
- Recently added
- Alphabetically

## Usage

### Save/Update Alias
```python
from skills.address_book.scripts.manage_contacts import save_contact

save_contact(
    address="TXXXabc...",
    alias="朋友的钱包",
    increment_count=True
)
```

### Get Alias
```python
alias = get_contact_alias("TXXXabc...")
# Returns: "朋友的钱包" or None
```

### List All Contacts
```python
contacts = list_contacts(sort_by="count")
# Returns sorted list with aliases and transfer counts
```

## Data Storage

Contacts stored in: `skills/address-book/data/contacts.json`

```json
{
  "TXXXabc...": {
    "alias": "朋友的钱包",
    "transfer_count": 5,
    "first_seen": "2026-02-08T02:10:00",
    "last_transfer": "2026-02-08T10:30:00"
  }
}
```

## Integration with Transfer

**Automatic behavior in transfer-tokens:**
1. User transfers with memo → Save memo as alias
2. User transfers without memo → Increment count only
3. Display: "Sending to 朋友的钱包 (TXXXabc...)" instead of just address

## Privacy & Security

- 📁 Local storage only (not shared)
- 🔒 No sensitive data stored (addresses are public)
- ✅ User can edit/delete aliases anytime
- 🚫 Never store private keys or transaction details

## Commands

| Action | Example |
|--------|---------|
| Save alias | `save_contact("TXXXabc", "Alice的钱包")` |
| Get alias | `get_contact_alias("TXXXabc")` |
| List all | `list_contacts()` |
| Delete | `delete_contact("TXXXabc")` |
| Search | `search_contacts("Alice")` |

## Output Example

```
📇 Your Address Book
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Most Frequently Used:
  1. 家人钱包 (TXXXabc...abc) - 15 transfers
  2. 朋友-Alice (TYYYdef...def) - 8 transfers
  3. 交易所充值 (TZZZghi...ghi) - 3 transfers

Total contacts: 3
```
