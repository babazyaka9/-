import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const AnatomyApp());
}

class AnatomyApp extends StatelessWidget {
  const AnatomyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Анатомія',
      theme: ThemeData(
        primarySwatch: Colors.blue,
        scaffoldBackgroundColor: const Color(0xFFF5F5F5), // Світло-сірий фон як на сайті
        useMaterial3: true,
      ),
      home: const MenuScreen(),
    );
  }
}

// --- ГОЛОВНЕ МЕНЮ ---
class MenuScreen extends StatefulWidget {
  const MenuScreen({super.key});

  @override
  State<MenuScreen> createState() => _MenuScreenState();
}

class _MenuScreenState extends State<MenuScreen> {
  List<dynamic> _questions = [];
  Map<String, dynamic> _progress = {};
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      // Завантаження питань
      final jsonString = await rootBundle.loadString('questions.json');
      final List<dynamic> data = json.decode(jsonString);

      // Завантаження прогресу
      final prefs = await SharedPreferences.getInstance();
      final savedProgress = prefs.getString('user_progress');
      Map<String, dynamic> progressMap = {
        "wrong_indices": [],
        "chunk_results": {}
      };
      
      if (savedProgress != null) {
        progressMap = json.decode(savedProgress);
      }

      if (mounted) {
        setState(() {
          _questions = data;
          _progress = progressMap;
          _isLoading = false;
        });
      }
    } catch (e) {
      // Ігноруємо помилки, просто показуємо пустий екран або лоадер
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _resetProgress() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_progress');
    _loadData();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final wrongIndices = List<int>.from(_progress['wrong_indices'] ?? []);
    final chunkResults = _progress['chunk_results'] ?? {};
    const chunkSize = 40;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Анатомія", style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete_outline, color: Colors.red),
            onPressed: _resetProgress,
          )
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Кнопка помилок
          if (wrongIndices.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(bottom: 15),
              decoration: BoxDecoration(
                color: Colors.purple,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [BoxShadow(color: Colors.purple.withOpacity(0.3), blurRadius: 8, offset: const Offset(0, 4))],
              ),
              child: ListTile(
                leading: const Icon(Icons.warning_amber_rounded, color: Colors.white, size: 30),
                title: Text("Робота над помилками (${wrongIndices.length})",
                    style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                trailing: const Icon(Icons.arrow_forward_ios, color: Colors.white70, size: 16),
                onTap: () => _startQuiz(context, mode: 'review', wrongIds: wrongIndices),
              ),
            ),
          
          // Список тестів
          ...List.generate((_questions.length / chunkSize).ceil(), (index) {
            final start = index * chunkSize;
            final end = (start + chunkSize) < _questions.length ? (start + chunkSize) : _questions.length;
            final key = "$start-$end";
            final res = chunkResults[key];
            
            String status = "Не почато";
            IconData icon = Icons.circle_outlined;
            Color iconColor = Colors.grey;
            Color cardColor = Colors.white;

            if (res != null) {
              final percent = res['percent'];
              status = "${res['score']}/${res['total']} (${percent.toInt()}%)";
              if (percent >= 60) {
                icon = Icons.check_circle;
                iconColor = Colors.green;
                cardColor = Colors.green.shade50;
              } else {
                icon = Icons.cancel;
                iconColor = Colors.red;
                cardColor = Colors.red.shade50;
              }
            }

            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              decoration: BoxDecoration(
                color: cardColor,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: ListTile(
                leading: Icon(icon, color: iconColor, size: 28),
                title: Text("Тест ${index + 1}", style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(status),
                onTap: () => _startQuiz(context, mode: 'chunk', start: start, end: end, key: key),
              ),
            );
          }),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  void _startQuiz(BuildContext context, {required String mode, int? start, int? end, String? key, List<int>? wrongIds}) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => QuizScreen(
          allQuestions: _questions,
          mode: mode,
          start: start ?? 0,
          end: end ?? 0,
          chunkKey: key,
          wrongIds: wrongIds,
          currentProgress: _progress,
        ),
      ),
    );
    _loadData(); // Оновлюємо меню після повернення
  }
}

// --- ЕКРАН ТЕСТУ ---
class QuizScreen extends StatefulWidget {
  final List<dynamic> allQuestions;
  final String mode;
  final int start;
  final int end;
  final String? chunkKey;
  final List<int>? wrongIds;
  final Map<String, dynamic> currentProgress;

  const QuizScreen({
    super.key,
    required this.allQuestions,
    required this.mode,
    required this.start,
    required this.end,
    this.chunkKey,
    this.wrongIds,
    required this.currentProgress,
  });

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  List<dynamic> _quizQuestions = [];
  int _currentIndex = 0;
  int _score = 0;
  List<int> _newWrongs = [];
  List<int> _correctIds = [];
  bool _answered = false;
  int? _selectedOption;

  @override
  void initState() {
    super.initState();
    if (widget.mode == 'chunk') {
      _quizQuestions = widget.allQuestions.sublist(widget.start, widget.end);
    } else {
      _quizQuestions = widget.allQuestions.where((q) => widget.wrongIds!.contains(q['id'])).toList();
    }
  }

  void _checkAnswer(int index) {
    setState(() {
      _selectedOption = index;
      _answered = true;
      final q = _quizQuestions[_currentIndex];
      final correct = q['c'];
      final id = q['id'];

      if (index == correct) {
        _score++;
        _correctIds.add(id);
      } else {
        _newWrongs.add(id);
      }
    });
  }

  void _nextQuestion() {
    if (_currentIndex < _quizQuestions.length - 1) {
      setState(() {
        _currentIndex++;
        _answered = false;
        _selectedOption = null;
      });
    } else {
      _finishQuiz();
    }
  }

  Future<void> _finishQuiz() async {
    final prefs = await SharedPreferences.getInstance();
    
    // Оновлюємо помилки
    Set<int> wrongSet = Set<int>.from(widget.currentProgress['wrong_indices'] ?? []);
    wrongSet.addAll(_newWrongs);
    wrongSet.removeAll(_correctIds);
    widget.currentProgress['wrong_indices'] = wrongSet.toList();

    // Оновлюємо статистику
    if (widget.mode == 'chunk' && widget.chunkKey != null) {
      double percent = (_score / _quizQuestions.length) * 100;
      Map<String, dynamic> chunkRes = widget.currentProgress['chunk_results'] ?? {};
      chunkRes[widget.chunkKey!] = {
        "score": _score,
        "total": _quizQuestions.length,
        "percent": percent
      };
      widget.currentProgress['chunk_results'] = chunkRes;
    }

    await prefs.setString('user_progress', json.encode(widget.currentProgress));

    if (!mounted) return;
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (context) => ResultScreen(score: _score, total: _quizQuestions.length)),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_quizQuestions.isEmpty) return const Scaffold(body: Center(child: Text("Помилок немає! 🎉")));

    final q = _quizQuestions[_currentIndex];

    // СКРОЛЛ ВІДБУВАЄТЬСЯ ТУТ (SingleChildScrollView)
    return Scaffold(
      appBar: AppBar(
        title: Text("Питання ${_currentIndex + 1}/${_quizQuestions.length}"),
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.black),
          onPressed: () => Navigator.of(context).pop(),
        ),
        titleTextStyle: const TextStyle(color: Colors.black, fontSize: 18, fontWeight: FontWeight.bold),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(q['q'], style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600, height: 1.4)),
              const SizedBox(height: 30),
              
              // Варіанти відповідей
              ...List.generate(q['opts'].length, (index) {
                Color bgColor = Colors.white;
                Color textColor = Colors.black87;
                Color borderColor = Colors.grey.shade300;

                if (_answered) {
                  if (index == q['c']) {
                    bgColor = Colors.green.shade500; // Правильна - зелена
                    textColor = Colors.white;
                    borderColor = Colors.green.shade500;
                  } else if (index == _selectedOption) {
                    bgColor = Colors.red.shade400; // Обрана неправильна - червона
                    textColor = Colors.white;
                    borderColor = Colors.red.shade400;
                  }
                }

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: InkWell(
                    onTap: _answered ? null : () => _checkAnswer(index),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: bgColor,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: borderColor, width: 1.5),
                        boxShadow: [
                          if (!_answered)
                            BoxShadow(color: Colors.grey.withOpacity(0.1), blurRadius: 4, offset: const Offset(0, 2))
                        ],
                      ),
                      child: Text(q['opts'][index], style: TextStyle(color: textColor, fontSize: 16)),
                    ),
                  ),
                );
              }),
              
              const SizedBox(height: 20),
              
              // Кнопка Далі
              if (_answered)
                SizedBox(
                  height: 55,
                  child: ElevatedButton(
                    onPressed: _nextQuestion,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.blueAccent,
                      foregroundColor: Colors.white,
                      elevation: 4,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text("Далі", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ),
              const SizedBox(height: 20), // Відступ знизу для зручного скролу
            ],
          ),
        ),
      ),
    );
  }
}

class ResultScreen extends StatelessWidget {
  final int score;
  final int total;

  const ResultScreen({super.key, required this.score, required this.total});

  @override
  Widget build(BuildContext context) {
    double percent = (score / total) * 100;
    bool passed = percent >= 60;

    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(passed ? Icons.check_circle_rounded : Icons.cancel_rounded, 
                 size: 100, color: passed ? Colors.green : Colors.red),
            const SizedBox(height: 20),
            Text("${percent.toInt()}%", 
                 style: TextStyle(fontSize: 48, fontWeight: FontWeight.bold, color: passed ? Colors.green : Colors.red)),
            const SizedBox(height: 10),
            Text("Правильно: $score з $total", style: const TextStyle(fontSize: 20, color: Colors.grey)),
            const SizedBox(height: 40),
            SizedBox(
              width: 200,
              height: 50,
              child: ElevatedButton(
                onPressed: () => Navigator.of(context).pop(),
                style: ElevatedButton.styleFrom(
                  backgroundColor: passed ? Colors.green : Colors.blue,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: const Text("В меню", style: TextStyle(fontSize: 18)),
              ),
            )
          ],
        ),
      ),
    );
  }
}
