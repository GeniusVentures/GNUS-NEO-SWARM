import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_chat_core/flutter_chat_core.dart';
import 'package:flutter_chat_ui/flutter_chat_ui.dart';
import 'package:flutter_slm_bridge/flutter_slm_bridge.dart';

void main() {
  // Initialise the SLM engine with the real Mistral-7B MNN model.
  geniusSlmInit(
    modelPath:
        '/Volumes/Work/Gnus_ai/genius-llm-v1/models/mistral-7b-mnn/llm.mnn',
  );
  runApp(const GeniusSwarmApp());
}

class GeniusSwarmApp extends StatelessWidget {
  const GeniusSwarmApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'GNUS NEO SWARM',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6C3CE1), // GNUS purple
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const GeniusChatScreen(),
    );
  }
}

class GeniusChatScreen extends StatefulWidget {
  const GeniusChatScreen({super.key});

  @override
  GeniusChatScreenState createState() => GeniusChatScreenState();
}

class GeniusChatScreenState extends State<GeniusChatScreen> {
  final _chatController = InMemoryChatController();
  bool _isThinking = false;
  bool _modelLoaded = false;
  String _engineMode = 'stub';

  @override
  void initState() {
    super.initState();
    _checkEngineStatus();
  }

  void _checkEngineStatus() {
    final status = getEngineStatus();
    try {
      final map = jsonDecode(status) as Map<String, dynamic>;
      setState(() {
        _modelLoaded = map['model_loaded'] as bool? ?? false;
        _engineMode = map['mode'] as String? ?? 'stub';
      });
    } catch (_) {
      setState(() {
        _modelLoaded = false;
        _engineMode = 'stub';
      });
    }
  }

  @override
  void dispose() {
    _chatController.dispose();
    super.dispose();
  }

  Future<void> _onMessageSend(String text) async {
    if (text.trim().isEmpty) return;

    // Insert user message immediately
    await _chatController.insertMessage(
      TextMessage(
        id: _newId(),
        authorId: 'user',
        createdAt: DateTime.now().toUtc(),
        text: text,
      ),
    );

    setState(() => _isThinking = true);

    try {
      // Build OpenAI v1 request
      final requestJson = jsonEncode({
        'model': 'genius-neo-swarm',
        'messages': [
          {'role': 'user', 'content': text}
        ],
      });

      // Call native bridge on a helper isolate (non-blocking)
      final responseJson = await chatCompletionsCreateAsync(requestJson);
      final content = extractContent(responseJson);

      await _chatController.insertMessage(
        TextMessage(
          id: _newId(),
          authorId: 'assistant',
          createdAt: DateTime.now().toUtc(),
          text: content,
        ),
      );
    } catch (e) {
      await _chatController.insertMessage(
        TextMessage(
          id: _newId(),
          authorId: 'assistant',
          createdAt: DateTime.now().toUtc(),
          text: 'Error: $e',
        ),
      );
    } finally {
      setState(() => _isThinking = false);
    }
  }

  String _newId() => '${Random().nextInt(1 << 30)}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('GNUS NEO SWARM'),
        actions: [
          if (_isThinking)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Center(
                child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            ),
        ],
      ),
      body: Column(
        children: [
          // Stub mode banner
          if (!_modelLoaded)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              color: Colors.orange.shade900.withOpacity(0.9),
              child: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded,
                      color: Colors.orangeAccent, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Running in stub mode — no model loaded. '
                      'Responses are simulated. '
                      'Pass a .mnn model path to geniusSlmInit() for real inference.',
                      style: TextStyle(
                        color: Colors.orange.shade100,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          // Chat area
          Expanded(
            child: Chat(
              chatController: _chatController,
              currentUserId: 'user',
              onMessageSend: _onMessageSend,
              resolveUser: (UserID id) async {
                if (id == 'user') return const User(id: 'user', name: 'You');
                return const User(id: 'assistant', name: 'GNUS Swarm');
              },
            ),
          ),
        ],
      ),
    );
  }
}
