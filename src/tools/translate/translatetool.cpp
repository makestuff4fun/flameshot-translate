// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Brian Barrett

#include "translatetool.h"

TranslateTool::TranslateTool(QObject* parent)
  : AbstractActionTool(parent)
{}

bool TranslateTool::closeOnButtonPressed() const
{
    return false;
}

QIcon TranslateTool::icon(const QColor& background, bool inEditor) const
{
    Q_UNUSED(inEditor)
    return QIcon(iconPath(background) + "translate.svg");
}

QString TranslateTool::name() const
{
    return tr("Translate");
}

CaptureTool::Type TranslateTool::type() const
{
    return CaptureTool::TYPE_TRANSLATE;
}

QString TranslateTool::description() const
{
    return tr("Translate Chinese text in the selection to English");
}

CaptureTool* TranslateTool::copy(QObject* parent)
{
    return new TranslateTool(parent);
}

void TranslateTool::pressed(CaptureContext& context)
{
    Q_UNUSED(context)
    emit requestAction(REQ_TRANSLATE);
}
