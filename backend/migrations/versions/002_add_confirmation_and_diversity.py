"""add confirmation requests table and diversity columns

Revision ID: 20260601_0004
Revises: 20260601_0003
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260601_0004'
down_revision = '20260601_0003'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 创建 confirmation_requests 表
    op.create_table(
        'confirmation_requests',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('ai_tasks.id'), nullable=False),
        sa.Column('workflow_id', sa.String(50), nullable=False),
        sa.Column('point_id', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('summary', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='pending'),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('human_input', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index('ix_confirmation_task_id', 'confirmation_requests', ['task_id'])
    op.create_index('ix_confirmation_status', 'confirmation_requests', ['status'])
    
    # 扩展 ai_tasks 表
    op.add_column('ai_tasks', sa.Column('mode', sa.String(20), server_default='confirm'))
    op.add_column('ai_tasks', sa.Column('current_workflow_id', sa.String(50), nullable=True))
    op.add_column('ai_tasks', sa.Column('current_confirmation_point', sa.String(50), nullable=True))
    op.add_column('ai_tasks', sa.Column('chain_position', sa.Integer(), nullable=True))
    op.add_column('ai_tasks', sa.Column('human_input', sa.Text(), nullable=True))
    
    # 扩展 characters 表
    op.add_column('characters', sa.Column('personality_vector', postgresql.JSONB(), nullable=True))
    
    # 创建 content_embeddings 表
    op.create_table(
        'content_embeddings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('novel_projects.id'), nullable=False),
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('embedding', postgresql.JSONB(), nullable=False),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index('ix_content_embeddings_project', 'content_embeddings', ['project_id'])
    op.create_index('ix_content_embeddings_type', 'content_embeddings', ['content_type'])

def downgrade() -> None:
    op.drop_table('content_embeddings')
    op.drop_column('characters', 'personality_vector')
    op.drop_column('ai_tasks', 'human_input')
    op.drop_column('ai_tasks', 'chain_position')
    op.drop_column('ai_tasks', 'current_confirmation_point')
    op.drop_column('ai_tasks', 'current_workflow_id')
    op.drop_column('ai_tasks', 'mode')
    op.drop_index('ix_confirmation_status', 'confirmation_requests')
    op.drop_index('ix_confirmation_task_id', 'confirmation_requests')
    op.drop_table('confirmation_requests')
