import type { Expression, Parser } from 'expr-eval';

const sampleIndex = Symbol('counterSampleIndex');
type SampleScope = Record<string, number> & { [sampleIndex]: number };

interface Instruction {
    type: string;
    value: string | number | Instruction[] | ((scope: SampleScope) => number);
}

interface InstructionExpression extends Expression {
    tokens: Instruction[];
}

export function createSampleEvaluator(parser: Parser, expression: Expression, values: Record<string, number>[]): (index: number) => unknown {
    let hasSampleOperations = false;

    function fromInstructions(tokens: Instruction[]): Expression {
        const result = parser.parse('0') as InstructionExpression;
        result.tokens = tokens;
        return result;
    }

    function evaluate(parsed: Expression, index: number): unknown {
        const scope: SampleScope = { ...values[index], [sampleIndex]: index };
        return parsed.evaluate(scope);
    }

    function numericOperand(tokens: Instruction[], name: string): (index: number) => number {
        const argument = fromInstructions(tokens);
        const cache = new Map<number, number>();
        return (index) => {
            const cached = cache.get(index);
            if (cached !== undefined) return cached;
            const value = evaluate(argument, index);
            if (typeof value !== 'number') throw new Error(`${name} expects a numeric expression`);
            cache.set(index, value);
            return value;
        };
    }

    function difference(tokens: Instruction[], stepTokens?: Instruction[]): Instruction {
        const operand = numericOperand(tokens, 'd');
        const stepExpression = stepTokens ? fromInstructions(stepTokens) : undefined;
        return { type: 'IEXPREVAL',
            value: (scope: SampleScope) => {
                const index = scope[sampleIndex];
                const step = stepExpression ? evaluate(stepExpression, index) : 1;
                if (typeof step !== 'number' || !Number.isInteger(step) || step <= 0) throw new Error('d expects a positive integer sample step');
                return index < step ? NaN : operand(index) - operand(index - step);
            } };
    }

    function summation(tokens: Instruction[], countTokens?: Instruction[]): Instruction {
        const operand = numericOperand(tokens, 's');
        const countExpression = countTokens ? fromInstructions(countTokens) : undefined;
        const prefix = [0];
        const blocks = new Map<number, number>();

        function summand(index: number): number {
            const value = operand(index);
            return Number.isNaN(value) ? 0 : value;
        }

        // Cache disjoint range sums instead of subtracting prefixes: infinities
        // and overflow outside the selected window must not poison its result.
        function rangeSum(start: number, end: number, left = 0, right = values.length, node = 1): number {
            if (right <= start || left >= end) return 0;
            const covered = start <= left && right <= end;
            const cached = covered ? blocks.get(node) : undefined;
            if (cached !== undefined) return cached;
            let result: number;
            if (right - left === 1) result = summand(left);
            else {
                const middle = Math.floor((left + right) / 2);
                result = rangeSum(start, end, left, middle, node * 2) + rangeSum(start, end, middle, right, node * 2 + 1);
            }
            if (covered) blocks.set(node, result);
            return result;
        }

        return { type: 'IEXPREVAL',
            value: (scope: SampleScope) => {
                const index = scope[sampleIndex];
                if (countExpression) {
                    const count = evaluate(countExpression, index);
                    if (typeof count !== 'number' || !Number.isInteger(count) || count <= 0) throw new Error('s expects a positive integer sample count');
                    return rangeSum(Math.max(0, index - count + 1), index + 1);
                }
                while (prefix.length <= index + 1) {
                    const next = prefix.length - 1;
                    prefix.push(prefix[next] + summand(next));
                }
                return prefix[index + 1];
            } };
    }

    // Use expr-eval's parsed postfix instructions; retain its lazy conditional branches.
    function transform(tokens: Instruction[]): Instruction[] {
        const output: Instruction[] = [];
        const starts: number[] = [];
        for (const original of tokens) {
            const token = original.type === 'IEXPR' ? { ...original, value: transform(original.value as Instruction[]) } : original;
            if (token.type === 'IENDSTATEMENT') {
                starts.pop();
                output.push(token);
                continue;
            }
            let arity = 0;
            switch (token.type) {
                case 'IOP1':
                case 'IMEMBER': arity = 1; break;
                case 'IOP2': arity = 2; break;
                case 'IOP3': arity = 3; break;
                case 'IARRAY': arity = token.value as number; break;
                case 'IFUNCALL': arity = (token.value as number) + 1; break;
                case 'IFUNDEF': arity = (token.value as number) + 2; break;
            }
            const operands = starts.splice(starts.length - arity, arity);
            const start = operands[0] ?? output.length;
            const fn = output[start];
            if (token.type === 'IFUNCALL' && fn?.type === 'IVAR' && (fn.value === 'd' || fn.value === 's') && (operands[1] ?? output.length) === start + 1) {
                hasSampleOperations = true;
                if (token.value !== 1 && token.value !== 2) throw new Error(`${fn.value} expects one expression and an optional sample ${fn.value === 'd' ? 'step' : 'count'}`);
                const argument = output.slice(operands[1], operands[2]);
                const step = token.value === 2 ? output.slice(operands[2]) : undefined;
                // Resolve the lazy value before expr-eval tests it as a condition or logical operand.
                output.splice(start, output.length - start, fn.value === 'd' ? difference(argument, step) : summation(argument, step), { type: 'IOP1', value: '+' });
            } else output.push(token);
            starts.push(start);
        }
        return output;
    }

    const transformed = fromInstructions(transform((expression as InstructionExpression).tokens));
    return hasSampleOperations ? (index) => evaluate(transformed, index) : (index): unknown => expression.evaluate(values[index]);
}
