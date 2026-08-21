package com.animus.smartroom.overlay.view

import android.annotation.SuppressLint
import android.content.Context
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.ViewConfiguration
import android.widget.FrameLayout
import kotlin.math.abs

/**
 * Custom FrameLayout overlay container that intercepts drag gestures before child Compose views
 * without breaking child clicks on buttons (Mic, Close, Open, Cancel).
 */
class DraggableOverlayContainer @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : FrameLayout(context, attrs, defStyleAttr) {

    private val touchSlop = ViewConfiguration.get(context).scaledTouchSlop.coerceAtLeast(16)

    private var initialRawX = 0f
    private var initialRawY = 0f
    private var isDragging = false

    var onDragStart: (() -> Unit)? = null
    var onDragMove: ((deltaX: Int, deltaY: Int) -> Unit)? = null
    var onDragEnd: ((wasDragging: Boolean) -> Unit)? = null

    override fun onInterceptTouchEvent(ev: MotionEvent): Boolean {
        when (ev.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                initialRawX = ev.rawX
                initialRawY = ev.rawY
                isDragging = false
                // Do not intercept DOWN so child clickables get the event
                return false
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = ev.rawX - initialRawX
                val dy = ev.rawY - initialRawY
                if (!isDragging && (abs(dx) > touchSlop || abs(dy) > touchSlop)) {
                    isDragging = true
                    onDragStart?.invoke()
                    // Steal the touch stream from children for dragging!
                    return true
                }
            }
            MotionEvent.ACTION_CANCEL, MotionEvent.ACTION_UP -> {
                if (isDragging) {
                    isDragging = false
                    onDragEnd?.invoke(true)
                    return true
                }
            }
        }
        return isDragging
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun onTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                initialRawX = event.rawX
                initialRawY = event.rawY
                isDragging = false
                return true
            }
            MotionEvent.ACTION_MOVE -> {
                val dx = (event.rawX - initialRawX).toInt()
                val dy = (event.rawY - initialRawY).toInt()
                if (!isDragging && (abs(dx) > touchSlop || abs(dy) > touchSlop)) {
                    isDragging = true
                    onDragStart?.invoke()
                }
                if (isDragging) {
                    onDragMove?.invoke(dx, dy)
                    return true
                }
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                val wasDragging = isDragging
                isDragging = false
                onDragEnd?.invoke(wasDragging)
                return wasDragging
            }
        }
        return super.onTouchEvent(event)
    }
}
