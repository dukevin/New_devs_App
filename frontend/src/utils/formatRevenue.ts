export function formatRevenue(amount: string): string {
  const [whole, cents] = amount.split('.');
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${cents}`;
}
