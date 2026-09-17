import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/home_shell.dart';
import '../providers/auth_provider.dart';
import 'signup_screen.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);

    ref.listen(authControllerProvider, (previous, next) {
      if (!next.isLoading && !next.hasError && previous?.isLoading == true) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const HomeShell()),
        );
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Log in')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              key: const Key('email_field'),
              controller: _emailController,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('password_field'),
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            if (authState.hasError)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(
                  'Login failed: ${authState.error}',
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            ElevatedButton(
              key: const Key('login_button'),
              onPressed: authState.isLoading
                  ? null
                  : () => ref.read(authControllerProvider.notifier).signIn(
                        _emailController.text,
                        _passwordController.text,
                      ),
              child: authState.isLoading
                  ? const CircularProgressIndicator()
                  : const Text('Log in'),
            ),
            TextButton(
              key: const Key('go_to_signup_link'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SignupScreen()),
              ),
              child: const Text("Don't have an account? Sign up"),
            ),
          ],
        ),
      ),
    );
  }
}
