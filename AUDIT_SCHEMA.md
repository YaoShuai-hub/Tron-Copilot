# Audit Log Schema (audit.v1)

This schema standardizes all audit records written to JSONL logs.

## Top-Level Fields

- `schema_version` (string) : Always `audit.v1`
- `event_id` (string) : UUID for this audit record
- `ts` (string) : UTC timestamp, `YYYY-MM-DDTHH:MM:SSZ`
- `event_type` (string) : `request` | `build` | `sign` | `broadcast` | `confirm` | `reconcile` | `error` | `custom`
- `source` (string) : Module/source name
- `actor` (object) : Who/what initiated the action
- `request` (object) : User intent / parameters
- `transaction` (object) : Transaction details (txid, raw, amounts)
- `result` (object) : Success/failure outcome
- `tags` (array) : Optional list of tags
- `meta` (object) : Extra structured data
- `payload` (object) : Original raw event (only present if auto-normalized)

## Actor Object

- `type` (string) : `user` | `agent` | `system`
- `id` (string)
- `session_id` (string)
- `ip` (string)
- `user_agent` (string)

## Request Object

- `action` (string) : `transfer` | `deposit` | `withdraw` | ...
- `asset` (string) : `TRX` | `TRC20` | `USDT` | ...
- `from` (string)
- `to` (string)
- `amount` (string)
- `amount_raw` (string)
- `token_contract` (string)
- `network` (string)

## Transaction Object

- `unsigned_txid` (string)
- `signed_txid` (string)
- `txid` (string)
- `raw_data_hex` (string)
- `expiration` (int)
- `block_number` (int)
- `block_time` (int)
- `fee_sun` (int)
- `energy_usage` (int)

## Result Object

- `success` (bool)
- `code` (string)
- `message` (string)
- `raw` (object)

## Example (Normalized)

```json
{
  "schema_version": "audit.v1",
  "event_id": "b6a4b1d0-0e2a-4bd0-88e0-6ecb45c9a4f8",
  "ts": "2026-02-07T12:00:00Z",
  "event_type": "broadcast",
  "source": "chain_transfer_flow",
  "actor": {"type": "user", "id": "henry"},
  "request": {"action": "transfer", "asset": "TRX", "from": "T...", "to": "T...", "amount": "1.25"},
  "transaction": {"txid": "..."},
  "result": {"success": true, "raw": {"result": true}},
  "tags": ["tron", "transfer"],
  "meta": {}
}
```
