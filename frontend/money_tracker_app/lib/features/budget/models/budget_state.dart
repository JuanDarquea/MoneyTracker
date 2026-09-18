class BudgetLine {
  BudgetLine({
    required this.categoryId,
    required this.categoryName,
    required this.isEssential,
    required this.budgetAmount,
    required this.source,
    required this.eligibleForSuggestion,
    required this.actualThisMonth,
    this.isArchived = false,
  });

  final String categoryId;
  final String categoryName;
  final bool isEssential;
  final String? budgetAmount;
  final String? source;
  final bool eligibleForSuggestion;
  final String actualThisMonth;
  final bool isArchived;

  factory BudgetLine.fromJson(Map<String, dynamic> json) => BudgetLine(
        categoryId: json['category_id'] as String,
        categoryName: json['category_name'] as String,
        isEssential: json['is_essential'] as bool,
        budgetAmount: json['budget_amount'] as String?,
        source: json['source'] as String?,
        eligibleForSuggestion: json['eligible_for_suggestion'] as bool,
        actualThisMonth: json['actual_this_month'] as String,
        isArchived: json['is_archived'] as bool? ?? false,
      );
}

class BudgetState {
  BudgetState({
    required this.incomeTarget,
    required this.actualIncomeThisMonth,
    required this.lines,
    required this.essentialsBudgetTotal,
    required this.discretionaryBudgetTotal,
    required this.essentialsActualTotal,
    required this.discretionaryActualTotal,
    required this.projectedNet,
    required this.actualNetSoFar,
  });

  final String? incomeTarget;
  final String actualIncomeThisMonth;
  final List<BudgetLine> lines;
  final String essentialsBudgetTotal;
  final String discretionaryBudgetTotal;
  final String essentialsActualTotal;
  final String discretionaryActualTotal;
  final String? projectedNet;
  final String actualNetSoFar;

  factory BudgetState.fromJson(Map<String, dynamic> json) => BudgetState(
        incomeTarget: json['income_target'] as String?,
        actualIncomeThisMonth: json['actual_income_this_month'] as String,
        lines: (json['lines'] as List<dynamic>)
            .map((item) => BudgetLine.fromJson(item as Map<String, dynamic>))
            .toList(),
        essentialsBudgetTotal: json['essentials_budget_total'] as String,
        discretionaryBudgetTotal: json['discretionary_budget_total'] as String,
        essentialsActualTotal: json['essentials_actual_total'] as String,
        discretionaryActualTotal: json['discretionary_actual_total'] as String,
        projectedNet: json['projected_net'] as String?,
        actualNetSoFar: json['actual_net_so_far'] as String,
      );
}

class BudgetSuggestion {
  BudgetSuggestion({required this.categoryId, required this.isEssential, required this.suggestedAmount});

  final String categoryId;
  final bool isEssential;
  final String suggestedAmount;

  factory BudgetSuggestion.fromJson(Map<String, dynamic> json) => BudgetSuggestion(
        categoryId: json['category_id'] as String,
        isEssential: json['is_essential'] as bool,
        suggestedAmount: json['suggested_amount'] as String,
      );
}
