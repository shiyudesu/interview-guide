package interview.guide.modules.voiceinterview.repository;

import interview.guide.modules.voiceinterview.model.VoiceInterviewMessageEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 语音面试消息Repository
 */
@Repository
public interface VoiceInterviewMessageRepository extends JpaRepository<VoiceInterviewMessageEntity, Long> {

    /**
     * 根据会话ID查找所有消息，按序号升序排列
     */
    List<VoiceInterviewMessageEntity> findBySessionIdOrderBySequenceNumAsc(Long sessionId);

    List<VoiceInterviewMessageEntity> findBySessionIdAndMessageTypeNotOrderBySequenceNumAsc(
        Long sessionId, String messageType);

    Optional<VoiceInterviewMessageEntity>
        findFirstBySessionIdAndUserRecognizedTextIsNullAndAiGeneratedTextIsNotNullOrderBySequenceNumDesc(
            Long sessionId);

    long countBySessionId(Long sessionId);

    long countBySessionIdAndMessageTypeNot(Long sessionId, String messageType);

    void deleteBySessionId(Long sessionId);

    Optional<VoiceInterviewMessageEntity> findFirstBySessionIdAndMessageTypeOrderBySequenceNumAsc(
        Long sessionId, String messageType);

}
