import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class Home extends StatelessWidget {
  const Home({super.key});

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    print('width $width');
    return FutureBuilder(
      future: loadBudgets(),
      builder: (context, snapshot) {
        return ListView(
          shrinkWrap: true,
          children: (snapshot.data ?? []).map((b) => Text(b)).toList(),
        );
      },
    );
  }
}

Future<List<String>> loadBudgets() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString('auth_token', 'x');
  // print('commented out');
  return ['a'];
}

const api = 'http://api.example.com/v1';
