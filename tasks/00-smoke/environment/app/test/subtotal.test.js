import { test } from "node:test";
import assert from "node:assert/strict";
import { subtotal } from "../src/cart.js";

test("subtotal sums price * qty", () => {
  assert.equal(subtotal([{ price: 10, qty: 2 }, { price: 5, qty: 1 }]), 25);
});

test("subtotal of an empty cart is 0", () => {
  assert.equal(subtotal([]), 0);
});
