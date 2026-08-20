package com.animus.smartroom.command.parser

import com.animus.smartroom.command.model.AnimusCommand

interface CommandParser {
    fun parse(input: String): AnimusCommand
}
