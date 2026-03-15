class User {
  final int userId;
  final String email;
  final String fullName;
  final String? phone;
  final String role;
  final DateTime createdAt;

  User({
    required this.userId,
    required this.email,
    required this.fullName,
    this.phone,
    required this.role,
    required this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      userId: json['user_id'],
      email: json['email'],
      fullName: json['full_name'],
      phone: json['phone'],
      role: json['role'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'email': email,
      'full_name': fullName,
      'phone': phone,
      'role': role,
      'created_at': createdAt.toIso8601String(),
    };
  }
}

class LoginRequest {
  final String email;
  final String password;

  LoginRequest({
    required this.email,
    required this.password,
  });

  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'password': password,
    };
  }
}

class RegisterRequest {
  final String email;
  final String password;
  final String fullName;
  final String? phone;

  RegisterRequest({
    required this.email,
    required this.password,
    required this.fullName,
    this.phone,
  });

  Map<String, dynamic> toJson() {
    return {
      'email': email,
      'password': password,
      'full_name': fullName,
      'phone': phone,
    };
  }
}

class Token {
  final String accessToken;
  final String tokenType;
  final int expiresIn;

  Token({
    required this.accessToken,
    required this.tokenType,
    required this.expiresIn,
  });

  factory Token.fromJson(Map<String, dynamic> json) {
    return Token(
      accessToken: json['access_token'],
      tokenType: json['token_type'],
      expiresIn: json['expires_in'],
    );
  }
}

class ChatMessage {
  final int? messageId;
  final String sender;
  final String messageText;
  final DateTime createdAt;
  final double? confidence;
  final bool isProcessing;

  ChatMessage({
    this.messageId,
    required this.sender,
    required this.messageText,
    required this.createdAt,
    this.confidence,
    this.isProcessing = false,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      messageId: json['message_id'],
      sender: json['sender'],
      messageText: json['message_text'],
      createdAt: DateTime.parse(json['created_at']),
      confidence: json['confidence']?.toDouble(),
      isProcessing: json['is_processing'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'message_id': messageId,
      'sender': sender,
      'message_text': messageText,
      'created_at': createdAt.toIso8601String(),
      'confidence': confidence,
      'is_processing': isProcessing,
    };
  }
}

class ChatSession {
  final int sessionId;
  final String title;
  final DateTime createdAt;
  final int messageCount;

  ChatSession({
    required this.sessionId,
    required this.title,
    required this.createdAt,
    required this.messageCount,
  });

  factory ChatSession.fromJson(Map<String, dynamic> json) {
    return ChatSession(
      sessionId: json['session_id'],
      title: json['title'],
      createdAt: DateTime.parse(json['created_at']),
      messageCount: json['message_count'],
    );
  }
}

class ChatRequest {
  final String message;
  final String? conversationId;

  ChatRequest({
    required this.message,
    this.conversationId,
  });

  Map<String, dynamic> toJson() {
    return {
      'message': message,
      'conversation_id': conversationId,
    };
  }
}

class ChatResponse {
  final String response;
  final List<Map<String, dynamic>> sources;
  final double confidence;
  final String? conversationId;

  ChatResponse({
    required this.response,
    required this.sources,
    required this.confidence,
    this.conversationId,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      response: json['response'],
      sources: List<Map<String, dynamic>>.from(json['sources']),
      confidence: json['confidence'].toDouble(),
      conversationId: json['conversation_id'],
    );
  }
}

class Document {
  final int id;
  final String title;
  final String? docNumber;
  final String? issuingAgency;
  final String? docType;
  final DateTime? signingDate;
  final DateTime? effectiveDate;
  final DateTime? expiryDate;
  final String? status;
  final String? summary;
  final String? htmlContent;
  final String? textContent;
  final String? sourceUrl;
  final String? fileUrl;
  final DateTime? createdAt;

  Document({
    required this.id,
    required this.title,
    this.docNumber,
    this.issuingAgency,
    this.docType,
    this.signingDate,
    this.effectiveDate,
    this.expiryDate,
    this.status,
    this.summary,
    this.htmlContent,
    this.textContent,
    this.sourceUrl,
    this.fileUrl,
    this.createdAt,
  });

  factory Document.fromJson(Map<String, dynamic> json) {
    return Document(
      id: json['id'],
      title: json['title'],
      docNumber: json['doc_number'],
      issuingAgency: json['issuing_agency'],
      docType: json['doc_type'],
      signingDate: json['signing_date'] != null 
          ? DateTime.parse(json['signing_date']) 
          : null,
      effectiveDate: json['effective_date'] != null 
          ? DateTime.parse(json['effective_date']) 
          : null,
      expiryDate: json['expiry_date'] != null 
          ? DateTime.parse(json['expiry_date']) 
          : null,
      status: json['status'],
      summary: json['summary'],
      htmlContent: json['html_content'],
      textContent: json['text_content'],
      sourceUrl: json['source_url'],
      fileUrl: json['file_url'],
      createdAt: json['created_at'] != null 
          ? DateTime.parse(json['created_at']) 
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'doc_number': docNumber,
      'issuing_agency': issuingAgency,
      'doc_type': docType,
      'signing_date': signingDate?.toIso8601String(),
      'effective_date': effectiveDate?.toIso8601String(),
      'expiry_date': expiryDate?.toIso8601String(),
      'status': status,
      'summary': summary,
      'html_content': htmlContent,
      'text_content': textContent,
      'source_url': sourceUrl,
      'file_url': fileUrl,
      'created_at': createdAt?.toIso8601String(),
    };
  }
}

class SavedDocument {
  final int documentId;
  final String title;
  final String? docNumber;
  final String? docType;
  final String? issuingAgency;
  final DateTime? effectiveDate;
  final String? status;
  final String? fileUrl;
  final String? sourceUrl;
  final DateTime savedAt;

  SavedDocument({
    required this.documentId,
    required this.title,
    this.docNumber,
    this.docType,
    this.issuingAgency,
    this.effectiveDate,
    this.status,
    this.fileUrl,
    this.sourceUrl,
    required this.savedAt,
  });

  factory SavedDocument.fromJson(Map<String, dynamic> json) {
    // Handle title - could be String or List
    String title;
    if (json['title'] is List) {
      title = (json['title'] as List).join(' ');
    } else {
      title = json['title']?.toString() ?? 'N/A';
    }
    
    // Handle saved_at - could be String or already DateTime
    DateTime savedAt;
    if (json['saved_at'] is String) {
      savedAt = DateTime.parse(json['saved_at']);
    } else if (json['saved_at'] is DateTime) {
      savedAt = json['saved_at'];
    } else {
      savedAt = DateTime.now(); // Fallback
    }
    
    return SavedDocument(
      documentId: json['id'] is int ? json['id'] : int.parse(json['id'].toString()),
      title: title,
      docNumber: json['doc_number']?.toString(),
      docType: json['doc_type']?.toString(),
      issuingAgency: json['issuing_agency']?.toString(),
      effectiveDate: json['effective_date'] != null
          ? (json['effective_date'] is String 
              ? DateTime.parse(json['effective_date'])
              : json['effective_date'] as DateTime)
          : null,
      status: json['status']?.toString(),
      fileUrl: json['file_url']?.toString(),
      sourceUrl: json['source_url']?.toString(),
      savedAt: savedAt,
    );
  }
}

class Collection {
  final int id;
  final String name;
  final String? description;
  final String? color;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final int documentCount;

  Collection({
    required this.id,
    required this.name,
    this.description,
    this.color,
    required this.createdAt,
    this.updatedAt,
    required this.documentCount,
  });

  factory Collection.fromJson(Map<String, dynamic> json) {
    return Collection(
      id: json['id'],
      name: json['name'],
      description: json['description'],
      color: json['color'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'])
          : null,
      documentCount: json['document_count'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'color': color,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'document_count': documentCount,
    };
  }
}

class CollectionDocument {
  final int id;
  final String title;
  final String? docNumber;
  final String? docType;
  final String? issuingAgency;
  final DateTime? effectiveDate;
  final String? status;
  final String? fileUrl;
  final String? sourceUrl;
  final String? notes;
  final DateTime addedAt;

  CollectionDocument({
    required this.id,
    required this.title,
    this.docNumber,
    this.docType,
    this.issuingAgency,
    this.effectiveDate,
    this.status,
    this.fileUrl,
    this.sourceUrl,
    this.notes,
    required this.addedAt,
  });

  factory CollectionDocument.fromJson(Map<String, dynamic> json) {
    return CollectionDocument(
      id: json['id'],
      title: json['title'],
      docNumber: json['doc_number'],
      docType: json['doc_type'],
      issuingAgency: json['issuing_agency'],
      effectiveDate: json['effective_date'] != null
          ? DateTime.parse(json['effective_date'])
          : null,
      status: json['status'],
      fileUrl: json['file_url'],
      sourceUrl: json['source_url'],
      notes: json['notes'],
      addedAt: DateTime.parse(json['added_at']),
    );
  }
}

class DocumentTag {
  final String tagName;
  final DateTime createdAt;

  DocumentTag({
    required this.tagName,
    required this.createdAt,
  });

  factory DocumentTag.fromJson(Map<String, dynamic> json) {
    return DocumentTag(
      tagName: json['tag_name'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

class CollectionCreateRequest {
  final String name;
  final String? description;
  final String? color;

  CollectionCreateRequest({
    required this.name,
    this.description,
    this.color,
  });

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      if (description != null) 'description': description,
      if (color != null) 'color': color,
    };
  }
}

class TagCreateRequest {
  final String tagName;

  TagCreateRequest({required this.tagName});

  Map<String, dynamic> toJson() {
    return {'tag_name': tagName};
  }
}

