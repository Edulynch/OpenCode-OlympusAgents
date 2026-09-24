export function calculateTotal(prices: number[]): number {
  return prices.reduce((total, price) => total + price, 0);
}
