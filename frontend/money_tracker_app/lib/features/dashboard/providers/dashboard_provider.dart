import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../models/monthly_summary.dart';

final monthlySummaryProvider = FutureProvider.autoDispose<MonthlySummary>((ref) async {
  final apiClient = ref.watch(apiClientProvider);
  final response = await apiClient.dio.get('/summary');
  return MonthlySummary.fromJson(response.data as Map<String, dynamic>);
});
