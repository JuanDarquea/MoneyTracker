import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../../../core/supabase_client.dart';

final authControllerProvider =
    StateNotifierProvider<AuthController, AsyncValue<void>>((ref) {
  return AuthController(ref.watch(supabaseClientProvider));
});

// Separate provider instance for SignupScreen. SignupScreen is pushed on
// top of LoginScreen (Navigator.push, not replace), so LoginScreen stays
// mounted underneath with its own ref.listen(authControllerProvider, ...)
// still active. If both screens shared authControllerProvider, a
// successful signup's loading->data transition would also satisfy
// LoginScreen's listener guard and navigate IT to TransactionEntryScreen
// behind the still-visible SignupScreen. A dedicated provider keeps the
// two screens' state independent.
final signupControllerProvider =
    StateNotifierProvider<AuthController, AsyncValue<void>>((ref) {
  return AuthController(ref.watch(supabaseClientProvider));
});

class AuthController extends StateNotifier<AsyncValue<void>> {
  AuthController(this._supabase) : super(const AsyncData(null));

  final SupabaseClient _supabase;

  Future<void> signIn(String email, String password) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _supabase.auth.signInWithPassword(email: email, password: password),
    );
  }

  Future<void> signUp(String email, String password) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => _supabase.auth.signUp(email: email, password: password),
    );
  }
}
