import {useCallback, useEffect, useMemo, useRef, useState, useTransition} from 'react';
import {AnimatePresence, motion} from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {Virtuoso, type VirtuosoHandle} from 'react-virtuoso';
import {knowledgeBaseApi, type KnowledgeBaseItem, type SortOption} from '../api/knowledgebase';
import {ragChatApi, type RagChatSessionListItem} from '../api/ragChat';
import {formatDateOnly} from '../utils/date';
import DeleteConfirmDialog from '../components/DeleteConfirmDialog';
import AiThinkingIndicator from '../components/AiThinkingIndicator';
import CodeBlock from '../components/CodeBlock';
import ResponsiveDialog from '../components/ResponsiveDialog';
import {BookOpen, ChevronLeft, ChevronRight, Edit, History, MessageSquare, Pin, Plus, Trash2, X,} from 'lucide-react';
import {useMediaQuery} from '../hooks/useMediaQuery';

interface KnowledgeBaseQueryPageProps {
  onBack: () => void;
  onUpload: () => void;
}

interface Message {
  id?: number;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface CategoryGroup {
  name: string;
  items: KnowledgeBaseItem[];
  isExpanded: boolean;
}

export default function KnowledgeBaseQueryPage({ onBack, onUpload }: KnowledgeBaseQueryPageProps) {
  const isCompact = useMediaQuery('(max-width: 1023px)');
  // 知识库状态
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseItem[]>([]);
  const [selectedKbIds, setSelectedKbIds] = useState<Set<number>>(new Set());
  const [loadingList, setLoadingList] = useState(true);

  // 搜索和排序状态
  const [searchKeyword, setSearchKeyword] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('time');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['未分类']));

  // 右侧面板状态
  const [rightPanelOpen, setRightPanelOpen] = useState(() => (
    typeof window === 'undefined' || !window.matchMedia('(max-width: 1023px)').matches
  ));
  const [leftPanelOpen, setLeftPanelOpen] = useState(false);

  // 会话状态
  const [sessions, setSessions] = useState<RagChatSessionListItem[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null);
  const [currentSessionTitle, setCurrentSessionTitle] = useState<string>('');
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [sessionDeleteConfirm, setSessionDeleteConfirm] = useState<{ id: number; title: string } | null>(null);
  const [editingSessionTitle, setEditingSessionTitle] = useState<{ id: number; title: string } | null>(null);
  const [newSessionTitle, setNewSessionTitle] = useState('');

  // 消息状态
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);

  // refs
  const virtuosoRef = useRef<VirtuosoHandle>(null);
  const rafRef = useRef<number>();

  const [, startTransition] = useTransition();

  const loadKnowledgeBases = useCallback(async () => {
    setLoadingList(true);
    try {
      // 问答助手只显示向量化完成的知识库
      const list = await knowledgeBaseApi.getAllKnowledgeBases(sortBy, 'COMPLETED');
      setKnowledgeBases(list);
    } catch (err) {
      console.error('加载知识库列表失败', err);
    } finally {
      setLoadingList(false);
    }
  }, [sortBy]);

  const handleSearch = async () => {
    if (!searchKeyword.trim()) {
      loadKnowledgeBases();
      return;
    }
    setLoadingList(true);
    try {
      const list = await knowledgeBaseApi.search(searchKeyword.trim());
      setKnowledgeBases(list);
    } catch (err) {
      console.error('搜索知识库失败', err);
    } finally {
      setLoadingList(false);
    }
  };

  const groupedKnowledgeBases = useMemo((): CategoryGroup[] => {
    const groups: Map<string, KnowledgeBaseItem[]> = new Map();

    knowledgeBases.forEach(kb => {
      const category = kb.category || '未分类';
      if (!groups.has(category)) {
        groups.set(category, []);
      }
      groups.get(category)!.push(kb);
    });

    const result: CategoryGroup[] = [];
    const sortedCategories = Array.from(groups.keys()).sort((a, b) => {
      if (a === '未分类') return 1;
      if (b === '未分类') return -1;
      return a.localeCompare(b);
    });

    sortedCategories.forEach(name => {
      result.push({
        name,
        items: groups.get(name)!,
        isExpanded: expandedCategories.has(name),
      });
    });

    return result;
  }, [knowledgeBases, expandedCategories]);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const list = await ragChatApi.listSessions();
      setSessions(list);
    } catch (err) {
      console.error('加载会话列表失败', err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!searchKeyword) {
      void loadKnowledgeBases();
    }
  }, [loadKnowledgeBases, searchKeyword]);

  useEffect(() => {
    if (isCompact) {
      setRightPanelOpen(false);
      setLeftPanelOpen(false);
    } else {
      setRightPanelOpen(true);
      setLeftPanelOpen(false);
    }
  }, [isCompact]);

  useEffect(() => {
    if (!isCompact || (!leftPanelOpen && !rightPanelOpen)) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isCompact, leftPanelOpen, rightPanelOpen]);

  const handleToggleKb = (kbId: number) => {
    setSelectedKbIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(kbId)) {
        newSet.delete(kbId);
      } else {
        newSet.add(kbId);
      }
      if (newSet.size !== prev.size && currentSessionId) {
        setCurrentSessionId(null);
        setCurrentSessionTitle('');
        setMessages([]);
      }
      return newSet;
    });
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setCurrentSessionTitle('');
    setMessages([]);
    if (isCompact) setLeftPanelOpen(false);
  };

  const handleLoadSession = async (sessionId: number) => {
    try {
      const detail = await ragChatApi.getSessionDetail(sessionId);
      setCurrentSessionId(detail.id);
      setCurrentSessionTitle(detail.title);
      setSelectedKbIds(new Set(detail.knowledgeBases.map(kb => kb.id)));
      setMessages(detail.messages.map(m => ({
        id: m.id,
        type: m.type,
        content: m.content,
        timestamp: new Date(m.createdAt),
      })));
      if (isCompact) setLeftPanelOpen(false);
    } catch (err) {
      console.error('加载会话失败', err);
    }
  };

  const handleDeleteSession = async () => {
    if (!sessionDeleteConfirm) return;
    try {
      await ragChatApi.deleteSession(sessionDeleteConfirm.id);
      await loadSessions();
      if (currentSessionId === sessionDeleteConfirm.id) {
        handleNewSession();
      }
      setSessionDeleteConfirm(null);
    } catch (err) {
      console.error('删除会话失败', err);
    }
  };

  const handleEditSessionTitle = (sessionId: number, currentTitle: string) => {
    setEditingSessionTitle({ id: sessionId, title: currentTitle });
    setNewSessionTitle(currentTitle);
  };

  const handleSaveSessionTitle = async () => {
    if (!editingSessionTitle || !newSessionTitle.trim()) return;
    try {
      await ragChatApi.updateSessionTitle(editingSessionTitle.id, newSessionTitle.trim());
      await loadSessions();
      if (currentSessionId === editingSessionTitle.id) {
        setCurrentSessionTitle(newSessionTitle.trim());
      }
      setEditingSessionTitle(null);
      setNewSessionTitle('');
    } catch (err) {
      console.error('更新会话标题失败', err);
    }
  };

  const handleTogglePin = async (sessionId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await ragChatApi.togglePin(sessionId);
      await loadSessions();
    } catch (err) {
      console.error('切换置顶状态失败', err);
    }
  };

  const formatMarkdown = (text: string): string => {
    if (!text) return '';
    return text
      // 处理转义换行符
      .replace(/\\n/g, '\n')
      // 确保标题 # 后有空格
      .replace(/^(#{1,6})([^\s#\n])/gm, '$1 $2')
      // 确保有序列表数字后有空格（如 1.xxx -> 1. xxx）
      .replace(/^(\s*)(\d+)\.([^\s\n])/gm, '$1$2. $3')
      // 确保无序列表 - 或 * 后有空格
      .replace(/^(\s*[-*])([^\s\n-])/gm, '$1 $2')
      // 压缩多余空行
      .replace(/\n{3,}/g, '\n\n');
  };

  const handleSubmitQuestion = async () => {
    if (!question.trim() || selectedKbIds.size === 0 || loading) return;

    const userQuestion = question.trim();
    setQuestion('');
    setLoading(true);

    let sessionId = currentSessionId;
    if (!sessionId) {
      try {
        const session = await ragChatApi.createSession(Array.from(selectedKbIds));
        sessionId = session.id;
        setCurrentSessionId(sessionId);
        setCurrentSessionTitle(session.title);
      } catch (err) {
        console.error('创建会话失败', err);
        setLoading(false);
        return;
      }
    }

    const userMessage: Message = {
      type: 'user',
      content: userQuestion,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);

    const assistantMessage: Message = {
      type: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, assistantMessage]);

    let fullContent = '';
    const updateAssistantMessage = (content: string) => {
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (lastIndex >= 0 && newMessages[lastIndex].type === 'assistant') {
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            content: content,
          };
        }
        return newMessages;
      });
    };

    try {
      await ragChatApi.sendMessageStream(
        sessionId,
        userQuestion,
        (chunk: string) => {
          fullContent += chunk;
          if (rafRef.current) {
            cancelAnimationFrame(rafRef.current);
          }
          rafRef.current = requestAnimationFrame(() => {
            startTransition(() => {
              updateAssistantMessage(fullContent);
            });
          });
        },
        () => {
          setLoading(false);
          loadSessions();
        },
        (error: Error) => {
          console.error('流式查询失败:', error);
          updateAssistantMessage(fullContent || error.message || '回答失败，请重试');
          setLoading(false);
        }
      );
    } catch (err) {
      console.error('发起流式查询失败:', err);
      updateAssistantMessage(err instanceof Error ? err.message : '回答失败，请重试');
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatTimeAgo = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes} 分钟前`;
    if (hours < 24) return `${hours} 小时前`;
    if (days < 7) return `${days} 天前`;
    return formatDateOnly(dateStr);
  };

  return (
    <div className="mx-auto max-w-7xl pb-4 pt-0 sm:pb-8 lg:px-4 lg:pb-10 lg:pt-8">
      {/* 头部 */}
      <div className="mb-4 flex flex-col gap-3 sm:mb-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-1">问答助手</h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm">选择知识库，向 AI 提问</p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:flex">
          <motion.button
            onClick={onUpload}
            className="min-h-11 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            上传知识库
          </motion.button>
          <motion.button
            onClick={onBack}
            className="min-h-11 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-700"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            返回
          </motion.button>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 lg:hidden">
        <button
          type="button"
          onClick={() => { setRightPanelOpen(false); setLeftPanelOpen(true); }}
          className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
        >
          <History className="h-4 w-4" /> 对话历史
        </button>
        <button
          type="button"
          onClick={() => { setLeftPanelOpen(false); setRightPanelOpen(true); }}
          className="flex min-h-11 items-center justify-center gap-2 rounded-xl border border-primary-200 bg-primary-50 px-3 text-sm font-medium text-primary-700 dark:border-primary-800 dark:bg-primary-900/30 dark:text-primary-300"
        >
          <BookOpen className="h-4 w-4" /> 知识库（{selectedKbIds.size}）
        </button>
      </div>

      {isCompact && (leftPanelOpen || rightPanelOpen) && (
        <button
          type="button"
          aria-label="关闭辅助面板"
          onClick={() => { setLeftPanelOpen(false); setRightPanelOpen(false); }}
          className="fixed inset-0 z-[60] h-full w-full bg-black/50 backdrop-blur-sm"
        />
      )}

      <div className="relative flex h-[calc(100dvh-14rem)] min-h-[480px] gap-4 lg:h-[calc(100dvh-10rem)]">
        {/* 左侧：对话历史 */}
        <div
          role={isCompact ? 'dialog' : undefined}
          aria-modal={isCompact ? 'true' : undefined}
          aria-label={isCompact ? '对话历史' : undefined}
          className={isCompact
          ? `fixed inset-2 z-[65] ${leftPanelOpen ? 'block' : 'hidden'}`
          : 'w-64 flex-shrink-0'}
        >
          <div
              className="bg-white dark:bg-slate-800 rounded-2xl p-4 shadow-sm h-full flex flex-col border border-slate-100 dark:border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-slate-800 dark:text-white">对话历史</h2>
              <div className="flex items-center gap-1">
                <motion.button
                  onClick={handleNewSession}
                  disabled={selectedKbIds.size === 0}
                  className="flex h-11 w-11 items-center justify-center rounded-lg text-primary-500 transition-colors hover:bg-primary-50 disabled:cursor-not-allowed disabled:opacity-50 dark:hover:bg-primary-900/30"
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title="新建对话"
                  aria-label="新建对话"
                >
                  <Plus className="w-5 h-5" />
                </motion.button>
                {isCompact && (
                  <button type="button" onClick={() => setLeftPanelOpen(false)} aria-label="关闭对话历史" className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-700">
                    <X className="h-5 w-5" />
                  </button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingSessions ? (
                <div className="text-center py-6">
                  <motion.div
                    className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full mx-auto"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                  />
                </div>
              ) : sessions.length === 0 ? (
                  <div className="text-center py-6 text-slate-400 dark:text-slate-500 text-sm">
                  暂无对话历史
                </div>
              ) : (
                <div className="space-y-2">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      onClick={() => handleLoadSession(session.id)}
                      className={`p-3 rounded-lg cursor-pointer transition-all group ${currentSessionId === session.id
                          ? 'bg-primary-50 dark:bg-primary-900/30 border border-primary-500'
                          : 'bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 border border-transparent'
                        } ${session.isPinned ? 'border-l-4 border-l-primary-500' : ''}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            {session.isPinned && (
                              <Pin className="w-3.5 h-3.5 text-primary-500 fill-primary-500 flex-shrink-0" />
                            )}
                            <p className="font-medium text-slate-800 dark:text-white text-sm truncate">{session.title}</p>
                          </div>
                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                            {session.messageCount} 条消息 · {formatTimeAgo(session.updatedAt)}
                          </p>
                        </div>
                        <div className="flex items-center gap-1 opacity-100 transition-all lg:opacity-0 lg:group-hover:opacity-100">
                          <button
                            onClick={(e) => handleTogglePin(session.id, e)}
                            className={`p-1 rounded transition-colors ${session.isPinned
                              ? 'text-primary-500 hover:text-primary-600'
                              : 'text-slate-400 hover:text-primary-500'
                              }`}
                            title={session.isPinned ? '取消置顶' : '置顶'}
                          >
                            <Pin className={`w-4 h-4 ${session.isPinned ? 'fill-primary-500' : ''}`} />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditSessionTitle(session.id, session.title);
                            }}
                            className="p-1 text-slate-400 hover:text-primary-500 rounded transition-colors"
                            title="编辑标题"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSessionDeleteConfirm({ id: session.id, title: session.title });
                            }}
                            className="p-1 text-slate-400 hover:text-red-500 rounded transition-colors"
                            title="删除"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 中间：聊天区域 */}
        <div className="flex-1 min-w-0">
          <div
              className="flex h-full flex-col rounded-2xl border border-slate-100 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
            {selectedKbIds.size > 0 ? (
              <>
                {/* 会话信息 */}
                <div className="p-4 border-b border-slate-200 dark:border-slate-600">
                  <h2 className="text-base font-semibold text-slate-800 dark:text-white">
                    {currentSessionTitle || (selectedKbIds.size === 1
                      ? knowledgeBases.find(kb => kb.id === Array.from(selectedKbIds)[0])?.name || '新对话'
                      : `${selectedKbIds.size} 个知识库 - 新对话`)}
                  </h2>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {Array.from(selectedKbIds).map(kbId => {
                      const kb = knowledgeBases.find(k => k.id === kbId);
                      return kb ? (
                          <span key={kbId}
                                className="px-2 py-0.5 bg-primary-50 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 text-xs rounded-full">
                          {kb.name}
                        </span>
                      ) : null;
                    })}
                  </div>
                </div>

                {/* 消息列表 */}
                <div className="flex-1 min-h-0 relative dark:bg-slate-800">
                  {messages.length === 0 ? (
                      <div
                          className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 dark:text-slate-500">
                      <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-50" />
                      <p className="text-sm">开始提问吧！</p>
                    </div>
                  ) : (
                    <Virtuoso
                      ref={virtuosoRef}
                      data={messages}
                      initialTopMostItemIndex={messages.length - 1}
                      followOutput="smooth"
                      className="h-full w-full"
                      itemContent={(index, msg) => {
                        const showThinking = loading
                          && index === messages.length - 1
                          && msg.type === 'assistant'
                          && !msg.content;
                        return (
                          <div className="pb-4 px-4 first:pt-4 dark:bg-slate-800">
                          {showThinking ? (
                            <AiThinkingIndicator
                              label="知识库助手"
                              message="正在检索知识库并组织回答"
                              slowMessage="知识库内容较多，AI 仍在整理回答，请稍候"
                            />
                          ) : (
                          <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[92%] rounded-2xl p-3 shadow-sm sm:max-w-[85%] sm:p-4 ${msg.type === 'user'
                                ? 'bg-primary-600 text-white'
                                  : 'bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-600 text-slate-800 dark:text-slate-100'
                              }`}
                            >
                              {msg.type === 'user' ? (
                                <p className="whitespace-pre-wrap leading-relaxed text-sm">{msg.content}</p>
                              ) : (
                                  <div className="prose prose-slate dark:prose-invert prose-sm max-w-none">
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                      // 自定义代码块渲染
                                      code: ({ className, children }) => {
                                        const match = /language-(\w+)/.exec(className || '');
                                        const isInline = !match;

                                        if (isInline) {
                                          return (
                                              <code
                                                  className="bg-slate-100 dark:bg-slate-600 text-primary-600 dark:text-primary-400 px-1.5 py-0.5 rounded-md text-sm font-normal">
                                              {children}
                                            </code>
                                          );
                                        }

                                        // 代码块使用 CodeBlock 组件
                                        return (
                                          <CodeBlock language={match[1]}>
                                            {String(children).replace(/\n$/, '')}
                                          </CodeBlock>
                                        );
                                      },
                                      // 禁用默认 pre 渲染，由 CodeBlock 处理
                                      pre: ({ children }) => <>{children}</>,
                                    }}
                                  >
                                    {formatMarkdown(msg.content)}
                                  </ReactMarkdown>
                                  {loading && index === messages.length - 1 && (
                                    <span className="inline-block w-0.5 h-5 bg-primary-500 ml-1 animate-pulse" />
                                  )}
                                </div>
                              )}
                            </div>
                          </motion.div>
                          )}
                        </div>
                        );
                      }}
                    />
                  )}
                </div>

                {/* 输入区域 */}
                <div className="safe-area-bottom border-t border-slate-200 p-3 dark:border-slate-600 sm:p-4">
                  <div className="flex gap-2 sm:gap-3">
                    <input
                      type="text"
                      value={question}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmitQuestion()}
                      placeholder="输入您的问题..."
                      className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-slate-900 placeholder-slate-400 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white sm:px-4"
                      disabled={loading}
                    />
                    <motion.button
                      onClick={handleSubmitQuestion}
                      disabled={!question.trim() || selectedKbIds.size === 0 || loading}
                      className="min-h-11 rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50 sm:px-5"
                      whileHover={{ scale: loading ? 1 : 1.02 }}
                      whileTap={{ scale: loading ? 1 : 0.98 }}
                    >
                      发送
                    </motion.button>
                  </div>
                </div>
              </>
            ) : (
                <div className="flex-1 flex items-center justify-center text-slate-400 dark:text-slate-500">
                <div className="text-center">
                  <svg className="w-12 h-12 mx-auto mb-3 opacity-50" viewBox="0 0 24 24" fill="none">
                    <path d="M21 15C21 15.5304 20.7893 16.0391 20.4142 16.4142C20.0391 16.7893 19.5304 17 19 17H7L3 21V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H19C19.5304 3 20.0391 3.21071 20.4142 3.58579C20.7893 3.96086 21 4.46957 21 5V15Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <p className="text-sm">请先选择知识库</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 右侧：知识库选择（简化版） */}
        <AnimatePresence>
          {rightPanelOpen && (
            <motion.div
              role={isCompact ? 'dialog' : undefined}
              aria-modal={isCompact ? 'true' : undefined}
              aria-label={isCompact ? '选择知识库' : undefined}
              initial={isCompact ? { x: '100%', opacity: 0 } : { width: 0, opacity: 0 }}
              animate={isCompact ? { x: 0, opacity: 1 } : { width: 280, opacity: 1 }}
              exit={isCompact ? { x: '100%', opacity: 0 } : { width: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className={isCompact ? 'fixed inset-2 z-[65] overflow-hidden' : 'flex-shrink-0 overflow-hidden'}
            >
              <div
                  className="flex h-full w-full flex-col rounded-2xl border border-slate-100 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800 lg:w-[280px]">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold text-slate-800 dark:text-white">选择知识库</h2>
                  <button
                    onClick={() => setRightPanelOpen(false)}
                    aria-label="关闭知识库选择"
                    className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
                  >
                    {isCompact ? <X className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
                  </button>
                </div>

                {/* 搜索框 */}
                <div className="flex gap-2 mb-3">
                  <input
                    type="text"
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="搜索..."
                    className="flex-1 px-3 py-1.5 text-sm border border-slate-200 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 bg-white dark:bg-slate-700 text-slate-900 dark:text-white placeholder-slate-400"
                  />
                  <button
                    onClick={handleSearch}
                    className="px-3 py-1.5 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600"
                  >
                    搜索
                  </button>
                </div>

                {/* 排序 */}
                <div className="mb-3">
                  <select
                    value={sortBy}
                    onChange={(e) => {
                      setSortBy(e.target.value as SortOption);
                      setSearchKeyword('');
                    }}
                    className="w-full px-2 py-1 text-xs border border-slate-200 dark:border-slate-600 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-500 bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-300"
                  >
                    <option value="time">时间排序</option>
                    <option value="size">大小排序</option>
                    <option value="access">访问排序</option>
                    <option value="question">提问排序</option>
                  </select>
                </div>

                {/* 知识库列表 */}
                <div className="flex-1 overflow-y-auto">
                  {loadingList ? (
                    <div className="text-center py-6">
                      <motion.div
                        className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full mx-auto"
                        animate={{ rotate: 360 }}
                        transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      />
                    </div>
                  ) : knowledgeBases.length === 0 ? (
                      <div className="text-center py-6 text-slate-500 dark:text-slate-400">
                      <p className="mb-2 text-sm">{searchKeyword ? '未找到' : '暂无知识库'}</p>
                      {!searchKeyword && (
                        <button onClick={onUpload} className="text-primary-500 hover:text-primary-600 font-medium text-sm">
                          立即上传
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {groupedKnowledgeBases.map((group) => (
                          <div key={group.name}
                               className="border border-slate-100 dark:border-slate-700 rounded-lg overflow-hidden">
                          <button
                            onClick={() => toggleCategory(group.name)}
                            className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <ChevronRight
                                className={`w-3.5 h-3.5 text-slate-400 transition-transform ${group.isExpanded ? 'rotate-90' : ''}`}
                              />
                              <span
                                  className="font-medium text-slate-700 dark:text-slate-300 text-sm">{group.name}</span>
                            </div>
                            <span className="text-xs text-slate-400">{group.items.length}</span>
                          </button>

                          <AnimatePresence>
                            {group.isExpanded && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="overflow-hidden"
                              >
                                <div className="p-2 space-y-1">
                                  {group.items.map((kb) => (
                                    <div
                                      key={kb.id}
                                      onClick={() => handleToggleKb(kb.id)}
                                      className={`p-2 rounded-lg cursor-pointer transition-all ${selectedKbIds.has(kb.id)
                                          ? 'bg-primary-50 dark:bg-primary-900/30 border border-primary-500'
                                          : 'bg-white dark:bg-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700 border border-transparent'
                                        }`}
                                    >
                                      <div className="flex items-center gap-2">
                                        <input
                                          type="checkbox"
                                          checked={selectedKbIds.has(kb.id)}
                                          onChange={() => handleToggleKb(kb.id)}
                                          onClick={(e) => e.stopPropagation()}
                                          className="w-3.5 h-3.5 text-primary-500 rounded focus:ring-primary-500"
                                        />
                                        <span
                                            className="font-medium text-slate-800 dark:text-white text-xs truncate flex-1">{kb.name}</span>
                                      </div>
                                      <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 ml-5">{formatFileSize(kb.fileSize)}</p>
                                    </div>
                                  ))}
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 收起状态下的展开按钮 */}
        {!rightPanelOpen && !isCompact && (
          <button
            onClick={() => setRightPanelOpen(true)}
            className="flex-shrink-0 w-10 bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 flex items-center justify-center hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
            title="展开知识库面板"
          >
            <ChevronRight className="w-5 h-5 text-slate-400" />
          </button>
        )}
      </div>

      {/* 删除会话确认弹窗 */}
      <DeleteConfirmDialog
        open={!!sessionDeleteConfirm}
        item={sessionDeleteConfirm ? { id: 0, title: sessionDeleteConfirm.title } : null}
        itemType="对话"
        onConfirm={handleDeleteSession}
        onCancel={() => setSessionDeleteConfirm(null)}
      />

      <ResponsiveDialog
        open={editingSessionTitle !== null}
        onClose={() => {
          setEditingSessionTitle(null);
          setNewSessionTitle('');
        }}
        title="编辑标题"
        size="sm"
        mobileMode="compact"
        footer={(
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => {
                setEditingSessionTitle(null);
                setNewSessionTitle('');
              }}
              className="min-h-11 rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 dark:border-slate-600 dark:text-slate-300"
            >取消</button>
            <button
              type="button"
              onClick={handleSaveSessionTitle}
              disabled={!newSessionTitle.trim()}
              className="min-h-11 rounded-xl bg-primary-500 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >保存</button>
          </div>
        )}
      >
        <input
          type="text"
          value={newSessionTitle}
          onChange={(e) => setNewSessionTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSaveSessionTitle()}
          placeholder="请输入新标题"
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 dark:border-slate-600 dark:bg-slate-700 dark:text-white"
          autoFocus
        />
      </ResponsiveDialog>
    </div>
  );
}
