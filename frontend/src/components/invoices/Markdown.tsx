import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const plugins = [remarkGfm]

export function Markdown({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={plugins} components={{
        img: ({ src, alt }) => typeof src === 'string' && src.startsWith('/api/invoices/')
          ? <img src={src} alt={alt} /> : <span>{alt}</span>,
      }}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
