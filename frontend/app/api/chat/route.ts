import { NextRequest, NextResponse } from 'next/server';

/**
 * AI Chat API Route
 * Streams responses from MCP server
 */

const MCP_SERVER_URL = process.env.MCP_SERVER_URL || 'http://localhost:8000';

export async function POST(req: NextRequest) {
    try {
        const { message, walletAddress } = await req.json();

        if (!message) {
            return NextResponse.json(
                { error: 'Message is required' },
                { status: 400 }
            );
        }

        // Create a streaming response
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
            async start(controller) {
                try {
                    // Call MCP server
                    const response = await fetch(`${MCP_SERVER_URL}/chat`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            message,
                            wallet_address: walletAddress,
                        }),
                    });

                    if (!response.ok) {
                        throw new Error(`MCP server error: ${response.statusText}`);
                    }

                    const reader = response.body?.getReader();
                    if (!reader) {
                        throw new Error('No reader available');
                    }

                    // Forward stream to client
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        controller.enqueue(value);
                    }

                    controller.close();
                } catch (error: any) {
                    // Send error message to client
                    const errorMessage = `Error: ${error.message || 'Unknown error'}`;
                    controller.enqueue(encoder.encode(errorMessage));
                    controller.close();
                }
            },
        });

        return new NextResponse(stream, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        });
    } catch (error: any) {
        console.error('API route error:', error);
        return NextResponse.json(
            { error: error.message || 'Internal server error' },
            { status: 500 }
        );
    }
}
