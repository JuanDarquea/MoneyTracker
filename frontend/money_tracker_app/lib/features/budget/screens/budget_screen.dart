import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/budget_state.dart';
import '../providers/budget_provider.dart';

class BudgetScreen extends ConsumerStatefulWidget {
  const BudgetScreen({super.key});

  @override
  ConsumerState<BudgetScreen> createState() => _BudgetScreenState();
}

class _BudgetScreenState extends ConsumerState<BudgetScreen> {
  final _incomeTargetController = TextEditingController();
  bool _incomeTargetSeeded = false;
  final Map<String, TextEditingController> _lineControllers = {};

  TextEditingController _controllerFor(String categoryId, bool isEssential) {
    final key = '$categoryId-$isEssential';
    return _lineControllers.putIfAbsent(key, () => TextEditingController());
  }

  @override
  void dispose() {
    _incomeTargetController.dispose();
    for (final controller in _lineControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final budgetAsync = ref.watch(budgetProvider);
    // Watched here (rather than lazily inside _BudgetLineTile) so its fetch
    // starts on the very first build alongside budgetProvider's. If it were
    // only watched once a line tile first builds (i.e. after budgetProvider
    // resolves), its future would lag budgetProvider's by a full frame.
    final suggestionsAsync = ref.watch(budgetSuggestionsProvider);
    final controllerState = ref.watch(budgetControllerProvider);

    ref.listen(budgetControllerProvider, (previous, next) {
      if (next.hasError) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update budget: ${next.error}')),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Budget')),
      body: budgetAsync.when(
        data: (state) {
          if (!_incomeTargetSeeded && state.incomeTarget != null) {
            _incomeTargetController.text = state.incomeTarget!;
            _incomeTargetSeeded = true;
          }
          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      key: const Key('income_target_field'),
                      controller: _incomeTargetController,
                      decoration: const InputDecoration(labelText: 'Income target'),
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    ),
                  ),
                  IconButton(
                    key: const Key('save_income_target_button'),
                    icon: const Icon(Icons.check),
                    onPressed: controllerState.isLoading
                        ? null
                        : () => ref
                            .read(budgetControllerProvider.notifier)
                            .setIncomeTarget(_incomeTargetController.text),
                  ),
                ],
              ),
              Text('Actual income: ${state.actualIncomeThisMonth}', key: const Key('actual_income')),
              const SizedBox(height: 12),
              Text(
                state.projectedNet != null
                    ? 'Projected net: ${state.projectedNet}'
                    : 'Projected net: set an income target',
                key: const Key('projected_net'),
              ),
              Text('Actual net so far: ${state.actualNetSoFar}', key: const Key('actual_net_so_far')),
              const SizedBox(height: 24),
              _BudgetSection(
                title: 'Essentials',
                budgetTotal: state.essentialsBudgetTotal,
                actualTotal: state.essentialsActualTotal,
                lines: state.lines.where((line) => line.isEssential).toList(),
                controllerFor: _controllerFor,
                suggestionsAsync: suggestionsAsync,
              ),
              const SizedBox(height: 24),
              _BudgetSection(
                title: 'Discretionary',
                budgetTotal: state.discretionaryBudgetTotal,
                actualTotal: state.discretionaryActualTotal,
                lines: state.lines.where((line) => !line.isEssential).toList(),
                controllerFor: _controllerFor,
                suggestionsAsync: suggestionsAsync,
              ),
            ],
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Failed to load budget: $error')),
      ),
    );
  }
}

class _BudgetSection extends StatelessWidget {
  const _BudgetSection({
    required this.title,
    required this.budgetTotal,
    required this.actualTotal,
    required this.lines,
    required this.controllerFor,
    required this.suggestionsAsync,
  });

  final String title;
  final String budgetTotal;
  final String actualTotal;
  final List<BudgetLine> lines;
  final TextEditingController Function(String categoryId, bool isEssential) controllerFor;
  final AsyncValue<List<BudgetSuggestion>> suggestionsAsync;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        Text('Budget: $budgetTotal — Actual: $actualTotal'),
        ...lines.map(
          (line) => _BudgetLineTile(
            line: line,
            controller: controllerFor(line.categoryId, line.isEssential),
            suggestionsAsync: suggestionsAsync,
          ),
        ),
      ],
    );
  }
}

BudgetSuggestion? _matchingSuggestion(List<BudgetSuggestion> suggestions, String categoryId, bool isEssential) {
  for (final suggestion in suggestions) {
    if (suggestion.categoryId == categoryId && suggestion.isEssential == isEssential) {
      return suggestion;
    }
  }
  return null;
}

class _BudgetLineTile extends ConsumerWidget {
  const _BudgetLineTile({required this.line, required this.controller, required this.suggestionsAsync});

  final BudgetLine line;
  final TextEditingController controller;
  final AsyncValue<List<BudgetSuggestion>> suggestionsAsync;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final keySuffix = '${line.categoryId}-${line.isEssential}';
    final hasBudget = line.budgetAmount != null;
    final fraction = hasBudget
        ? ((double.tryParse(line.actualThisMonth) ?? 0) / (double.tryParse(line.budgetAmount!) ?? 1))
            .clamp(0.0, 1.0)
        : 0.0;
    final suggestion = line.eligibleForSuggestion
        ? suggestionsAsync.maybeWhen(
            data: (suggestions) => _matchingSuggestion(suggestions, line.categoryId, line.isEssential),
            orElse: () => null,
          )
        : null;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${line.categoryName} (${line.isEssential ? 'Essential' : 'Discretionary'})'),
          if (hasBudget) ...[
            Text('${line.actualThisMonth} / ${line.budgetAmount}', key: Key('line_progress_$keySuffix')),
            FractionallySizedBox(
              widthFactor: fraction,
              alignment: Alignment.centerLeft,
              child: Container(height: 8, color: Theme.of(context).colorScheme.primary),
            ),
          ] else ...[
            Row(
              children: [
                Expanded(
                  child: TextField(
                    key: Key('line_amount_field_$keySuffix'),
                    controller: controller,
                    decoration: const InputDecoration(labelText: 'Set budget'),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  ),
                ),
                IconButton(
                  key: Key('save_line_button_$keySuffix'),
                  icon: const Icon(Icons.check),
                  onPressed: () => ref.read(budgetControllerProvider.notifier).setLine(
                        categoryId: line.categoryId,
                        isEssential: line.isEssential,
                        amount: controller.text,
                      ),
                ),
                if (suggestion != null)
                  TextButton(
                    key: Key('accept_suggestion_button_$keySuffix'),
                    onPressed: () => ref.read(budgetControllerProvider.notifier).acceptSuggestion(
                          categoryId: line.categoryId,
                          isEssential: line.isEssential,
                        ),
                    child: Text('Use suggestion: ${suggestion.suggestedAmount}'),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
