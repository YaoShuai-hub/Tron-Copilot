export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    transactions?: UnsignedTransaction[];
}

export interface UnsignedTransaction {
    txID?: string;
    raw_data: {
        contract: Array<{
            parameter: {
                value: {
                    owner_address?: string;
                    to_address?: string;
                    contract_address?: string;
                    amount?: number;
                    data?: string;
                };
                type_url: string;
            };
            type: string;
        }>;
        ref_block_bytes: string;
        ref_block_hash: string;
        expiration: number;
        timestamp: number;
    };
    visible?: boolean;
    raw_data_hex?: string;
    transaction?: any;  // Full transaction object for API use
    metadata?: {
        type?: string;
        token?: string;
        token_symbol?: string;
        amount?: number;
        recipient?: string;
        estimated_energy?: number;
        estimated_bandwidth?: number;
        instructions?: string[];
    };
}

export interface TransactionResult {
    txid: string;
    success: boolean;
    error?: string;
}

export type MessageState = 'streaming' | 'complete' | 'error';
export type TxState = 'idle' | 'renting' | 'signing' | 'broadcasting' | 'success' | 'error';
