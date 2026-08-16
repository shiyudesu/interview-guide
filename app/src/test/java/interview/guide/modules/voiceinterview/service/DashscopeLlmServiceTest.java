package interview.guide.modules.voiceinterview.service;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 占位类：原测试依赖已被移除的 {@code VoiceInterviewPromptService.RolePrompt} 内部类，以及
 * {@link DashscopeLlmService} 旧的 3 参构造器。当前 {@code DashscopeLlmService} 已改为 5 参构造器
 * （{@code LlmProviderRegistry, VoiceInterviewPromptService, ResumeRepository,
 * VoiceInterviewProperties, PromptSanitizer}），历史用例不再适用。
 *
 * <p>保留文件路径，待配合新 prompt 生成体系重写一份围绕 {@code chatWithSession} /
 * {@code streamChat} 流程的测试时直接覆盖此文件。</p>
 */
@Disabled(
    "Pending rewrite: RolePrompt removed in commit e6bebe7; DashscopeLlmService constructor "
        + "signature evolved in commit f87f435 / c433a50"
)
@DisplayName("Dashscope LLM 服务测试（待重写）")
class DashscopeLlmServiceTest {

    @Test
    void placeholder() {
        // 空占位，不写断言；整类 @Disabled。
    }
}
