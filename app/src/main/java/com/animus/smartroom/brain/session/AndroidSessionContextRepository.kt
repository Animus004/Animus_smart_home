package com.animus.smartroom.brain.session

import com.animus.smartroom.core.brain.session.AssistantSessionContext
import com.animus.smartroom.core.brain.session.AssistantSessionSummary

object AndroidSessionContextRepository {

    private val sessionContext = AssistantSessionContext()

    fun getSession(): AssistantSessionContext {
        return sessionContext
    }

    fun getSummary(): AssistantSessionSummary {
        return sessionContext.toSummary()
    }

    fun reset() {
        sessionContext.reset()
    }
}
