// Activity 4 - schema validation seen from the shell
const d = db.getSiblingDB("ecommerce");
const info = d.getCollectionInfos({name: "products"})[0].options;
print("validationLevel=" + info.validationLevel + "  validationAction=" + info.validationAction);
print("required: " + JSON.stringify(info.validator.$and[0].$jsonSchema.required));
print("cross-field rule: " + JSON.stringify(info.validator.$and[1]));
try {
  d.products.insertOne({sku: "SKU-9999999", name: "Bad product", brand: "X", category: "Laptops", price: -5,
                        mrp: 10, currency: "INR", inventory: {stock: 1, warehouse: "BLR-1"}, status: "active", created_at: new Date()});
} catch (e) {
  print("\ninsert with price = -5 -> REJECTED, code " + e.code + ": " + e.message);
  printjson(e.errInfo.details.clausesNotSatisfied[0].details.schemaRulesNotSatisfied[0].propertiesNotSatisfied[0]);
}
