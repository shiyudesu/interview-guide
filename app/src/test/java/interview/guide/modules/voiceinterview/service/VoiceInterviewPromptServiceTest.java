package interview.guide.modules.voiceinterview.service;

import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * 占位类：原测试依赖已被移除的 {@code VoiceInterviewPromptService.RolePrompt} 内部类
 * 与 {@code getRolePrompt(String)} 方法。自 commit {@code e6bebe7}（"refactor: 语音面试接入
 * SkillsTool + 全局代码清理"）起 {@link VoiceInterviewPromptService} 已改为只暴露
 * {@code generateSystemPromptWithContext(skillId, resumeText)}，历史用例不再适用。
 *
 * <p>保留文件路径，后续配合 SkillsTool 加载能力重写一份围绕 {@code generateSystemPromptWithContext}
 * 的新测试时直接覆盖此文件。</p>
 */
@Disabled("Pending rewrite: RolePrompt / getRolePrompt removed in commit e6bebe7")
@DisplayName("VoiceInterviewPromptService 测试（待重写）")
class VoiceInterviewPromptServiceTest {

    @Test
    void placeholder() {
        // 空占位，不写断言；整类 @Disabled。
    }
}
