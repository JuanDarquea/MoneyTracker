class CategoryBreakdown {
  CategoryBreakdown({
    required this.categoryId,
    required this.categoryName,
    required this.type,
    required this.amount,
  });

  final String categoryId;
  final String categoryName;
  final String type;
  final String amount;

  factory CategoryBreakdown.fromJson(Map<String, dynamic> json) => CategoryBreakdown(
        categoryId: json['category_id'] as String,
        categoryName: json['category_name'] as String,
        type: json['type'] as String,
        amount: json['amount'] as String,
      );
}

class MonthlySummary {
  MonthlySummary({
    required this.month,
    required this.totalIncome,
    required this.totalExpense,
    required this.net,
    required this.byCategory,
  });

  final String month;
  final String totalIncome;
  final String totalExpense;
  final String net;
  final List<CategoryBreakdown> byCategory;

  factory MonthlySummary.fromJson(Map<String, dynamic> json) => MonthlySummary(
        month: json['month'] as String,
        totalIncome: json['total_income'] as String,
        totalExpense: json['total_expense'] as String,
        net: json['net'] as String,
        byCategory: (json['by_category'] as List<dynamic>)
            .map((item) => CategoryBreakdown.fromJson(item as Map<String, dynamic>))
            .toList(),
      );
}
