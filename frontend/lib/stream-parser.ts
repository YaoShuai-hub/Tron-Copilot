/**
 * Smart Stream Parser
 * Detects <<<JSON...JSON>>> markers in AI stream and extracts transaction data
 */

export interface ParsedChunk {
    type: 'text' | 'transaction';
    content: string;
    transaction?: any;
}

export class StreamParser {
    private buffer: string = '';
    private inJsonBlock: boolean = false;
    private jsonBuffer: string = '';

    parse(chunk: string): ParsedChunk[] {
        const results: ParsedChunk[] = [];
        this.buffer += chunk;

        while (this.buffer.length > 0) {
            if (!this.inJsonBlock) {
                // Look for JSON start marker
                const startIdx = this.buffer.indexOf('<<<JSON');

                if (startIdx === -1) {
                    // No marker found, return all as text
                    if (this.buffer.length > 0) {
                        results.push({ type: 'text', content: this.buffer });
                        this.buffer = '';
                    }
                    break;
                }

                // Text before marker
                if (startIdx > 0) {
                    results.push({ type: 'text', content: this.buffer.substring(0, startIdx) });
                }

                // Start JSON block
                this.inJsonBlock = true;
                this.jsonBuffer = '';
                this.buffer = this.buffer.substring(startIdx + 7); // Skip <<<JSON
            } else {
                // Look for JSON end marker
                const endIdx = this.buffer.indexOf('JSON>>>');

                if (endIdx === -1) {
                    // End marker not found yet, buffer everything
                    this.jsonBuffer += this.buffer;
                    this.buffer = '';
                    break;
                }

                // Found end marker
                this.jsonBuffer += this.buffer.substring(0, endIdx);

                // Try to parse JSON
                try {
                    const transaction = JSON.parse(this.jsonBuffer);
                    results.push({
                        type: 'transaction',
                        content: '',
                        transaction,
                    });
                } catch (e) {
                    // Invalid JSON, treat as text
                    results.push({ type: 'text', content: this.jsonBuffer });
                }

                // Reset
                this.inJsonBlock = false;
                this.jsonBuffer = '';
                this.buffer = this.buffer.substring(endIdx + 7); // Skip JSON>>>
            }
        }

        return results;
    }

    reset() {
        this.buffer = '';
        this.inJsonBlock = false;
        this.jsonBuffer = '';
    }
}
