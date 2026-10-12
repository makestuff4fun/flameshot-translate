// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Brian Barrett

#include "translationlabeltool.h"

#include <QFontMetrics>

namespace {
// Smallest text we will shrink to before widening the box instead.
const int MIN_FONT_PX = 9;
// Horizontal breathing room inside the box, each side.
const int H_PAD = 2;
}

TranslationLabelTool::TranslationLabelTool(const QRect& rect,
                                           const QString& source,
                                           const QString& text,
                                           const QColor& background,
                                           const QColor& foreground,
                                           QObject* parent)
  : CaptureTool(parent)
  , m_rect(rect)
  , m_source(source)
  , m_text(text)
  , m_background(background)
  , m_foreground(foreground)
  , m_fontPx(0)
{
    fit();
}

// Choose a font size from the height of the Chinese, then shrink it a little
// if that makes the English fit the width. English usually runs longer than
// the Chinese it replaces, and shrinking it all the way makes neighbouring
// labels visibly different sizes, so past MAX_SHRINK the box grows to the
// right instead.
void TranslationLabelTool::fit()
{
    if (m_fontPx <= 0) {
        // OCR boxes are a little taller than the glyphs they hold.
        const int natural = qMax(MIN_FONT_PX, qRound(m_rect.height() * 0.68));
        const int smallest = qMax(MIN_FONT_PX, qRound(natural * 0.9));
        const int avail = m_rect.width() - 2 * H_PAD;
        m_fontPx = natural;
        m_font.setPixelSize(m_fontPx);
        while (m_fontPx > smallest &&
               QFontMetrics(m_font).horizontalAdvance(m_text) > avail) {
            m_font.setPixelSize(--m_fontPx);
        }
    }
    m_font.setPixelSize(m_fontPx);
    QFontMetrics fm(m_font);
    m_box = m_rect.adjusted(-1, -1, 1, 1);
    const int needW = fm.horizontalAdvance(m_text) + 2 * H_PAD;
    if (needW > m_box.width()) {
        m_box.setWidth(needW);
    }
    if (fm.height() > m_box.height()) {
        const int grow = fm.height() - m_box.height();
        m_box.adjust(0, -grow / 2, 0, grow - grow / 2);
    }
    m_pos = m_box.topLeft();
}

bool TranslationLabelTool::isValid() const
{
    return !m_text.isEmpty();
}

bool TranslationLabelTool::closeOnButtonPressed() const
{
    return false;
}

bool TranslationLabelTool::isSelectable() const
{
    return false;
}

bool TranslationLabelTool::showMousePreview() const
{
    return false;
}

QRect TranslationLabelTool::boundingRect() const
{
    return m_box;
}

QIcon TranslationLabelTool::icon(const QColor& background, bool inEditor) const
{
    Q_UNUSED(inEditor)
    return QIcon(iconPath(background) + "translate.svg");
}

QString TranslationLabelTool::name() const
{
    return tr("Translation");
}

QString TranslationLabelTool::description() const
{
    return tr("English translation of Chinese text");
}

QString TranslationLabelTool::info()
{
    return m_source + " → " + m_text;
}

CaptureTool::Type TranslationLabelTool::type() const
{
    return CaptureTool::TYPE_TRANSLATION_LABEL;
}

CaptureTool* TranslationLabelTool::copy(QObject* parent)
{
    auto* tool = new TranslationLabelTool(
      m_rect, m_source, m_text, m_background, m_foreground, parent);
    tool->m_fontPx = m_fontPx;
    tool->fit();
    copyParams(this, tool);
    return tool;
}

void TranslationLabelTool::process(QPainter& painter, const QPixmap& pixmap)
{
    Q_UNUSED(pixmap)
    painter.save();
    painter.fillRect(m_box, m_background);
    painter.setFont(m_font);
    painter.setPen(m_foreground);
    painter.drawText(m_box, Qt::AlignCenter | Qt::TextSingleLine, m_text);
    painter.restore();
}

void TranslationLabelTool::paintMousePreview(QPainter& painter,
                                             const CaptureContext& context)
{
    Q_UNUSED(painter)
    Q_UNUSED(context)
}

void TranslationLabelTool::move(const QPoint& pos)
{
    const QPoint delta = pos - m_box.topLeft();
    m_rect.translate(delta);
    m_box.translate(delta);
    m_pos = m_box.topLeft();
}

const QPoint* TranslationLabelTool::pos()
{
    return &m_pos;
}

void TranslationLabelTool::drawEnd(const QPoint& p)
{
    Q_UNUSED(p)
}

void TranslationLabelTool::drawMove(const QPoint& p)
{
    Q_UNUSED(p)
}

void TranslationLabelTool::drawStart(const CaptureContext& context)
{
    Q_UNUSED(context)
}

void TranslationLabelTool::pressed(CaptureContext& context)
{
    Q_UNUSED(context)
}

// The label keeps the colours it sampled from the screenshot; the editor's
// colour belongs to the drawing tools.
void TranslationLabelTool::onColorChanged(const QColor& c)
{
    Q_UNUSED(c)
}

// With a label selected, the size wheel resizes its text.
void TranslationLabelTool::onSizeChanged(int size)
{
    m_fontPx = qBound(MIN_FONT_PX, size, 96);
    fit();
}
