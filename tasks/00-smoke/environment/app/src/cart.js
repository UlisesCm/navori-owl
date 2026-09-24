export function subtotal(items) {
  return items.reduce((sum, item) => sum + item.price * item.qty, 0);
}

export function applyDiscount(amount, percent) {
  return amount * (percent / 100);
}

export function total(items, discountPercent = 0) {
  const base = subtotal(items);
  return discountPercent > 0 ? applyDiscount(base, discountPercent) : base;
}
