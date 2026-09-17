class TransactionDraft {
  TransactionDraft({
    required this.categoryId,
    required this.type,
    required this.amount,
    required this.occurredOn,
    this.note,
    this.isEssential,
  });

  final String categoryId;
  final String type;
  final String amount;
  final String occurredOn;
  final String? note;
  final bool? isEssential;

  Map<String, dynamic> toJson() => {
        'category_id': categoryId,
        'type': type,
        'amount': amount,
        'occurred_on': occurredOn,
        if (note != null && note!.isNotEmpty) 'note': note,
        if (isEssential != null) 'is_essential': isEssential,
      };
}
