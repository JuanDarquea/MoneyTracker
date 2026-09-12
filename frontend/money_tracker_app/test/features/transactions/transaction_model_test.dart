import 'package:flutter_test/flutter_test.dart';
import 'package:money_tracker_app/features/transactions/models/transaction.dart';

void main() {
  test('TransactionDraft serializes amount as a decimal string, not a double', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'expense',
      amount: '19.99',
      occurredOn: '2026-09-01',
      note: 'Lunch',
    );

    final json = draft.toJson();

    expect(json['amount'], '19.99');
    expect(json['amount'], isA<String>());
  });
}
