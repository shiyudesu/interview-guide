package interview.guide.modules.voiceinterview.context;

import interview.guide.common.ai.LlmProviderRegistry;
import interview.guide.modules.voiceinterview.config.VoiceInterviewProperties;
import interview.guide.modules.voiceinterview.model.VoiceInterviewMessageEntity;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.prompt.PromptTemplate;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 语音面试上下文压缩器。
 *
 * <p>将全量对话历史压缩为「最近窗口原文 + 早期轮次滚动摘要」，避免长会话下
 * 每轮把完整转录重发给 LLM 导致的 prompt token 无界增长与上下文溢出风险。
 *
 * <p>设计要点（详见 docs/语音面试上下文压缩_技术方案设计.md）：
 * <ul>
 *   <li>mode=NONE：不压缩，返回全部（默认行为，向后兼容）</li>
 *   <li>mode=WINDOW：仅保留最近 windowSize 轮原文，更早轮次丢弃</li>
 *   <li>mode=SUMMARY：保留最近窗口原文 + 早期轮次增量摘要（按 summaryBatchSize 触发，降低 LLM 摘要调用频率）</li>
 * </ul>
 */
@Slf4j
@Component
public class VoiceContextCompressor {

    private final LlmProviderRegistry llmProviderRegistry;
    private final VoiceInterviewProperties properties;
    private final PromptTemplate summaryPromptTemplate;

    public VoiceContextCompressor(LlmProviderRegistry llmProviderRegistry,
                                  VoiceInterviewProperties properties,
                                  ResourceLoader resourceLoader) {
        this.llmProviderRegistry = llmProviderRegistry;
        this.properties = properties;
        this.summaryPromptTemplate = loadTemplate(resourceLoader);
    }

    /**
     * 压缩对话历史。
     *
     * @param turns         全部对话轮次（不含 SUMMARY 行），按 sequenceNum 升序
     * @param cachedSummary 持久化已有的摘要（可能为 null）
     * @param coveredTurns  已被摘要覆盖的轮次数（用于增量合并，避免重复摘要）
     * @return 压缩结果：summary（可能为 null）、recent（保留的近期轮次）、coveredTurns、changed
     */
    public CompressedHistory compress(List<VoiceInterviewMessageEntity> turns,
                                       String cachedSummary, int coveredTurns) {
        return compress(turns, cachedSummary, coveredTurns, null);
    }

    /**
     * 使用会话指定的 LLM 提供商压缩对话历史。
     */
    public CompressedHistory compress(List<VoiceInterviewMessageEntity> turns,
                                       String cachedSummary, int coveredTurns,
                                       String llmProvider) {
        var cfg = properties.getContextCompression();
        // 未启用 / NONE 模式 / 未达到窗口大小：不压缩，返回全量（向后兼容）
        if (!cfg.isEnabled() || cfg.getMode() == VoiceInterviewProperties.Mode.NONE
                || turns.size() <= cfg.getWindowSize()) {
            return new CompressedHistory(null, turns, turns.size(), false);
        }

        int total = turns.size();
        int window = cfg.getWindowSize();
        int earlyCount = total - window;
        String summary = cachedSummary;
        boolean changed = false;
        int effectiveCoveredTurns = VoiceInterviewMessageEntity.trimToNull(cachedSummary) == null
            ? 0
            : Math.min(Math.max(coveredTurns, 0), earlyCount);

        if (cfg.getMode() == VoiceInterviewProperties.Mode.SUMMARY
                && earlyCount > effectiveCoveredTurns
                && earlyCount - effectiveCoveredTurns >= cfg.getSummaryBatchSize()) {
            // 仅对「尚未覆盖的早期轮次」做增量摘要合并，避免每轮都调用 LLM
            // earlyCount > coveredTurns 防御上游脏数据（如被损坏的 SUMMARY 行），避免 subList(from > to) 抛异常
            List<String> earlyTurns = formatRecent(turns.subList(effectiveCoveredTurns, earlyCount));
            String newSummary = summarize(cachedSummary, earlyTurns, llmProvider);
            if (newSummary != null && !newSummary.equals(cachedSummary)) {
                summary = newSummary;
                effectiveCoveredTurns = earlyCount;
                changed = true;
            } else {
                // 摘要未变化（或生成失败降级）：保持现状，不标记 changed，避免无谓持久化
                summary = newSummary != null ? newSummary : cachedSummary;
            }
        }

        int recentStart = cfg.getMode() == VoiceInterviewProperties.Mode.SUMMARY
            ? effectiveCoveredTurns
            : earlyCount;
        List<VoiceInterviewMessageEntity> recent = turns.subList(recentStart, total);
        return new CompressedHistory(summary, recent, effectiveCoveredTurns, changed);
    }

    /**
     * 将实体轮次格式化为「面试官：/候选人：」文本行，与原 getHistory 的格式化逻辑保持一致。
     */
    public List<String> formatRecent(List<VoiceInterviewMessageEntity> turns) {
        List<String> history = new ArrayList<>();
        String pendingAiQuestion = null;
        for (VoiceInterviewMessageEntity msg : turns) {
            String aiText = VoiceInterviewMessageEntity.trimToNull(msg.getAiGeneratedText());
            String userText = VoiceInterviewMessageEntity.trimToNull(msg.getUserRecognizedText());
            if (pendingAiQuestion != null) {
                history.add("面试官：" + pendingAiQuestion);
                pendingAiQuestion = null;
                if (userText != null) {
                    history.add("候选人：" + userText);
                }
                if (aiText != null) {
                    pendingAiQuestion = aiText;
                }
                continue;
            }
            if (aiText != null && userText != null) {
                history.add("面试官：" + aiText);
                history.add("候选人：" + userText);
            } else if (aiText != null) {
                pendingAiQuestion = aiText;
            } else if (userText != null) {
                history.add("候选人：" + userText);
            }
        }
        if (pendingAiQuestion != null) {
            history.add("面试官：" + pendingAiQuestion);
        }
        return history;
    }

    /**
     * 将早期轮次增量合并进已有摘要。摘要生成失败则降级沿用已有摘要，不阻塞主链路。
     */
    private String summarize(String prevSummary, List<String> earlyTurns, String llmProvider) {
        if (earlyTurns == null || earlyTurns.isEmpty()) {
            return prevSummary;
        }
        try {
            String prompt = summaryPromptTemplate.render(Map.of(
                "previousSummary", prevSummary == null ? "(空)" : prevSummary,
                "newTurns", String.join("\n", earlyTurns)
            ));
            // 使用不带 SkillsTool / MemoryAdvisor 的 plain client：摘要是纯文本压缩，
            // 不应混入面试素材工具，也不应让 MemoryAdvisor 重新注入完整历史（否则抵消压缩收益）
            String result = (llmProvider == null
                    ? llmProviderRegistry.getPlainChatClient()
                    : llmProviderRegistry.getPlainChatClient(llmProvider))
                    .prompt().user(prompt).call().content();
            return (result == null || result.isBlank()) ? prevSummary : result.trim();
        } catch (Exception e) {
            log.warn("上下文摘要生成失败，降级沿用已有摘要", e);
            return prevSummary;
        }
    }

    private static PromptTemplate loadTemplate(ResourceLoader resourceLoader) {
        try {
            String template = resourceLoader
                .getResource("classpath:prompts/voice-interview-context-summary.st")
                .getContentAsString(StandardCharsets.UTF_8);
            return new PromptTemplate(template);
        } catch (IOException e) {
            throw new IllegalStateException("加载语音面试上下文摘要模板失败", e);
        }
    }

    /**
     * 压缩结果。
     *
     * @param summary     早期轮次的滚动摘要（mode=SUMMARY 且已触发时非 null）
     * @param recent      保留的近期轮次实体（窗口内）
     * @param coveredTurns 已被摘要覆盖的轮次数
     * @param changed     摘要是否较缓存发生变化（需持久化）
     */
    public record CompressedHistory(String summary,
                                     List<VoiceInterviewMessageEntity> recent,
                                     int coveredTurns,
                                     boolean changed) {
    }
}
