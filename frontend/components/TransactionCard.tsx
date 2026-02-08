'use client';

import React, { useState, useCallback } from 'react';
import { useWallet } from '@tronweb3/tronwallet-adapter-react-hooks';
import { useNetwork } from '@/contexts/NetworkContext';
import { UnsignedTransaction, TxState } from '@/types/chat';
import { Check, X, Loader2, AlertCircle, ExternalLink } from 'lucide-react';

interface TransactionCardProps {
    transaction: UnsignedTransaction;
    onSuccess?: (txid: string) => void;
    onError?: (error: string) => void;
}

export const TransactionCard = React.memo(function TransactionCard({
    transaction,
    onSuccess,
    onError,
}: TransactionCardProps) {
    const { signTransaction, address } = useWallet();
    const { config: networkConfig } = useNetwork();
    const [state, setState] = useState<TxState>('idle');
    const [txid, setTxid] = useState<string>('');
    const [error, setError] = useState<string>('');
    const [rentEnergy, setRentEnergy] = useState<boolean>(true); // Default to rent energy

    const handleSignWithEnergy = useCallback(async () => {
        if (!signTransaction) {
            setError('钱包未连接');
            setState('error');
            return;
        }

        try {
            // Step 1: Rent energy if selected
            if (rentEnergy) {
                setState('renting');
                setError('');

                try {
                    const energyAmount = transaction.metadata?.estimated_energy || 28000;

                    const response = await fetch('http://localhost:8000/api/rent-energy', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            transaction: transaction,
                            recipient_address: transaction.metadata?.recipient || '',
                            network: networkConfig.name,
                            estimated_energy: energyAmount,
                        }),
                    });

                    if (!response.ok) {
                        throw new Error('Energy rental request failed');
                    }

                    const rentalResult = await response.json();
                    console.log('[TransactionCard] Energy rental result:', rentalResult);

                    if (rentalResult.success) {
                        // Show rental success message
                        setError(rentalResult.message);
                    } else {
                        setError(rentalResult.message || 'Energy rental failed, proceeding with transaction');
                    }

                    // Wait a bit to show the message
                    await new Promise(resolve => setTimeout(resolve, 1500));
                } catch (rentError: any) {
                    console.warn('Energy rental failed:', rentError);
                    setError('Energy rental failed, proceeding with transaction...');
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }

            // Step 2: Sign transaction
            setState('signing');
            setError('');

            console.log('[TransactionCard] About to sign transaction:', transaction);
            console.log('[TransactionCard] Transaction type:', typeof transaction);
            console.log('[TransactionCard] Transaction JSON:', JSON.stringify(transaction, null, 2));

            const signedTx = await signTransaction(transaction);

            console.log('[TransactionCard] Signed transaction:', signedTx);
            console.log('[TransactionCard] Signed transaction JSON:', JSON.stringify(signedTx, null, 2));

            setState('broadcasting');

            // Step 3: Broadcast to network
            const TronWeb = (await import('tronweb')).default;
            const tronWeb = new TronWeb({
                fullHost: networkConfig.trongridUrl, // Use detected network
            });

            console.log('[TransactionCard] Broadcasting to:', networkConfig.trongridUrl);
            const result = await tronWeb.trx.sendRawTransaction(signedTx);
            console.log('[TransactionCard] Broadcast result:', result);

            if (result.result) {
                const txid = result.txid || signedTx.txID || '';
                setTxid(txid);
                setState('success');
                onSuccess?.(txid);
            } else {
                console.error('[TransactionCard] Broadcast failed:', result);
                throw new Error(result.message || result.code || 'Transaction failed');
            }
        } catch (err: any) {
            const errorMsg = err.message || 'Unknown error';
            console.error('[TransactionCard] Transaction failed:', err);

            // Call error analysis API
            try {
                const analysisResponse = await fetch('http://localhost:8000/api/analyze-error', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        error_message: errorMsg,
                        error_context: 'broadcast',
                        transaction_details: {
                            type: transaction.raw_data?.contract?.[0]?.type,
                            network: networkConfig.name
                        }
                    })
                });

                if (analysisResponse.ok) {
                    const analysis = await analysisResponse.json();
                    console.log('[TransactionCard] Error analysis:', analysis);

                    // Format error message with analysis
                    const detailedError = `❌ **错误**：${errorMsg}\n\n` +
                        `📊 **分析**：\n${analysis.analysis}\n\n` +
                        `💡 **可能原因**：\n${analysis.possible_causes.map((c: string, i: number) => `${i + 1}. ${c}`).join('\n')}\n\n` +
                        `🔧 **建议**：\n${analysis.suggestions.map((s: string, i: number) => `${i + 1}. ${s}`).join('\n')}`;

                    setError(detailedError);
                } else {
                    setError(errorMsg);
                }
            } catch (analysisErr) {
                console.warn('[TransactionCard] Error analysis failed:', analysisErr);
                setError(errorMsg);
            }

            setState('error');
            onError?.(errorMsg);
        }
    }, [transaction, signTransaction, onSuccess, onError, rentEnergy, address, networkConfig]);

    const handleSign = useCallback(async () => {
        if (!signTransaction) {
            setError('Wallet not connected');
            setState('error');
            return;
        }

        try {
            setState('signing');

            // Sign transaction with wallet
            const signedTx = await signTransaction(transaction);

            setState('broadcasting');

            // Broadcast to network
            const TronWeb = (await import('tronweb')).default;
            const tronWeb = new TronWeb({
                fullHost: networkConfig.trongridUrl, // Use detected network
            });

            const result = await tronWeb.trx.sendRawTransaction(signedTx);

            if (result.result) {
                const txid = result.txid || signedTx.txID || '';
                setTxid(txid);
                setState('success');
                onSuccess?.(txid);
            } else {
                throw new Error(result.message || 'Transaction failed');
            }
        } catch (err: any) {
            const errorMsg = err.message || 'Unknown error';
            setError(errorMsg);
            setState('error');
            onError?.(errorMsg);
        }
    }, [transaction, signTransaction, onSuccess, onError]);

    const handleReject = useCallback(() => {
        setState('error');
        setError('Transaction rejected by user');
        onError?.('Rejected by user');
    }, [onError]);

    // Extract transaction details
    const contract = transaction.raw_data?.contract?.[0];
    const contractType = contract?.type || 'Unknown';
    const params = contract?.parameter?.value;

    return (
        <div className="glass-tron rounded-2xl p-6 shadow-2xl animate-slide-up">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-tron-500 animate-pulse" />
                    <h3 className="text-lg font-semibold text-white">
                        Transaction Preview
                    </h3>
                </div>
                {state !== 'idle' && (
                    <StateIndicator state={state} />
                )}
            </div>

            {/* Transaction Details */}
            <div className="space-y-3 mb-6">
                <DetailRow label="Type" value={contractType} />
                {params?.to_address && (
                    <DetailRow
                        label="To"
                        value={`${params.to_address.substring(0, 10)}...${params.to_address.substring(params.to_address.length - 8)}`}
                    />
                )}
                {params?.amount && (
                    <DetailRow
                        label="Amount"
                        value={`${(params.amount / 1e6).toFixed(2)} TRX`}
                    />
                )}
                {contract?.parameter?.type_url === 'type.googleapis.com/protocol.TriggerSmartContract' && (
                    <DetailRow label="Contract" value="Smart Contract Interaction" />
                )}
            </div>

            {/* Energy Rental Option */}
            {state === 'idle' && (
                <div className="mb-4 p-4 rounded-xl bg-purple-500/10 border border-purple-500/30">
                    <label className="flex items-center gap-3 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={rentEnergy}
                            onChange={(e) => setRentEnergy(e.target.checked)}
                            className="w-5 h-5 rounded border-2 border-purple-500/50 bg-transparent checked:bg-purple-500 checked:border-purple-500 cursor-pointer transition-all"
                        />
                        <div className="flex-1">
                            <div className="text-white font-medium">租赁能量 (推荐)</div>
                            <div className="text-sm text-gray-400">节省约 70% 手续费，仅需约 0.3 TRX</div>
                        </div>
                    </label>
                </div>
            )}

            {/* Action Buttons */}
            {state === 'idle' && (
                <div className="flex gap-3">
                    <button
                        onClick={handleReject}
                        className="flex-1 px-4 py-3 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-400 font-medium transition-all duration-150 hover:scale-105"
                    >
                        <div className="flex items-center justify-center gap-2">
                            <X className="w-5 h-5" />
                            拒绝
                        </div>
                    </button>
                    <button
                        onClick={handleSignWithEnergy}
                        disabled={!address}
                        className="flex-1 px-4 py-3 rounded-xl bg-gradient-to-r from-tron-500 to-tron-600 hover:from-tron-600 hover:to-tron-700 text-white font-medium transition-all duration-150 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <div className="flex items-center justify-center gap-2">
                            <Check className="w-5 h-5" />
                            确认并签名
                        </div>
                    </button>
                </div>
            )}

            {/* Loading State */}
            {(state === 'signing' || state === 'broadcasting') && (
                <div className="flex items-center justify-center gap-3 py-3">
                    <Loader2 className="w-5 h-5 animate-spin text-tron-500" />
                    <span className="text-gray-300">
                        {state === 'signing' ? 'Waiting for signature...' : 'Broadcasting transaction...'}
                    </span>
                </div>
            )}

            {/* Success State */}
            {state === 'success' && (
                <div className="space-y-3">
                    <div className="flex items-center justify-center gap-2 py-2">
                        <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center">
                            <Check className="w-5 h-5 text-green-400" />
                        </div>
                        <span className="text-green-400 font-medium">Transaction Successful!</span>
                    </div>
                    {txid && (
                        <a
                            href={`${networkConfig.tronscanUrl}/#/transaction/${txid}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center justify-center gap-2 text-sm text-tron-400 hover:text-tron-300 transition-colors"
                        >
                            View on TronScan
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    )}
                </div>
            )}

            {/* Error State */}
            {state === 'error' && (
                <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
                    <span className="text-red-400 text-sm">{error}</span>
                </div>
            )}
        </div>
    );
});

function StateIndicator({ state }: { state: TxState }) {
    const stateConfig = {
        signing: { color: 'text-blue-400', label: '签名中...' },
        renting: { color: 'text-purple-400', label: '租赁能量中...' },
        broadcasting: { color: 'text-yellow-400', label: '广播中...' },
        success: { color: 'text-green-400', label: '成功' },
        error: { color: 'text-red-400', label: '失败' },
        idle: { color: 'text-gray-400', label: '待签名' },
    };

    const config = stateConfig[state];

    return (
        <span className={`text-xs font-medium ${config.color}`}>
            {config.label}
        </span>
    );
}

function DetailRow({ label, value }: { label: string; value: string }) {
    return (
        <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span className="text-sm text-gray-400">{label}</span>
            <span className="text-sm text-white font-medium">{value}</span>
        </div>
    );
}
