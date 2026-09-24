import { calculateTotal } from '../src/cart';

if (calculateTotal([2, 3]) !== 5) throw new Error('cart total');
