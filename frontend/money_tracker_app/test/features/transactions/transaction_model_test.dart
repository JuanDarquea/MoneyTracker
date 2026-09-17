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

  test('TransactionDraft includes is_essential when provided', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'expense',
      amount: '19.99',
      occurredOn: '2026-09-01',
      isEssential: false,
    );

    expect(draft.toJson()['is_essential'], false);
  });

  test('TransactionDraft omits is_essential when null', () {
    final draft = TransactionDraft(
      categoryId: '11111111-1111-1111-1111-111111111111',
      type: 'income',
      amount: '1000.00',
      occurredOn: '2026-09-01',
    );

    expect(draft.toJson().containsKey('is_essential'), false);
  });
}
