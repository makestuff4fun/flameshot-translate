// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Brian Barrett

#pragma once

#include "tools/capturetool.h"

// One translated label: a box filled with the original label's background
// colour, with the English drawn in its text colour, sized to cover the
// Chinese it replaces. It behaves like any other annotation: it can be
// selected, moved, deleted and undone, and is part of the copied/saved image.
class TranslationLabelTool : public CaptureTool
{
    Q_OBJECT
public:
    TranslationLabelTool(const QRect& rect,
                         const QString& source,
                         const QString& text,
                         const QColor& background,
                         const QColor& foreground,
                         QObject* parent = nullptr);

    bool isValid() const override;
    bool closeOnButtonPressed() const override;
    bool isSelectable() const override;
    bool showMousePreview() const override;
    QRect boundingRect() const override;

    QIcon icon(const QColor& background, bool inEditor) const override;
    QString name() const override;
    QString description() const override;
    QString info() override;

    CaptureTool* copy(QObject* parent = nullptr) override;

    void process(QPainter& painter, const QPixmap& pixmap) override;
    void paintMousePreview(QPainter& painter,
                           const CaptureContext& context) override;

    void move(const QPoint& pos) override;
    const QPoint* pos() override;
    int size() const override { return m_fontPx; };

protected:
    CaptureTool::Type type() const override;

public slots:
    void drawEnd(const QPoint& p) override;
    void drawMove(const QPoint& p) override;
    void drawStart(const CaptureContext& context) override;
    void pressed(CaptureContext& context) override;
    void onColorChanged(const QColor& c) override;
    void onSizeChanged(int size) override;

private:
    void fit();

    QRect m_rect; // the area of the Chinese being covered
    QRect m_box;  // what is painted: m_rect, widened if the English needs it
    QPoint m_pos;
    QString m_source;
    QString m_text;
    QColor m_background;
    QColor m_foreground;
    QFont m_font;
    int m_fontPx; // 0 until fitted; the size wheel changes it afterwards
};
